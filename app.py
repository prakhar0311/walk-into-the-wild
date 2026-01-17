# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
import os
from datetime import datetime


# Create Flask app first
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
from models import db

db.init_app(app)
#db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models after db initialization
from models import User, Wildlife, Safari, CartItem, Order, OrderItem


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== ROUTES ====================

@app.route('/')
def index():
    safaris = Safari.query.limit(4).all()
    wildlife = Wildlife.query.limit(8).all()
    return render_template('index.html', safaris=safaris, wildlife=wildlife)


@app.route('/wildlife')
def wildlife_gallery():
    wildlife = Wildlife.query.all()
    return render_template('wildlife/gallery.html', wildlife=wildlife)

@app.route('/wildlife/<int:id>')
def wildlife_detail(id):
    animal = Wildlife.query.get_or_404(id)
    # Get similar wildlife (same category)
    similar = Wildlife.query.filter(
        Wildlife.category == animal.category,
        Wildlife.id != animal.id
    ).limit(3).all()
    return render_template('wildlife/detail.html', animal=animal, similar=similar)

@app.route('/safaris')
def safari_packages():
    safaris = Safari.query.all()
    return render_template('wildlife/packages.html', safaris=safaris)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))


@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = 0
    items = []

    for item in cart_items:
        if item.product_type == 'wildlife':
            product = Wildlife.query.get(item.product_id)
        else:
            product = Safari.query.get(item.product_id)

        if product:
            item_total = float(product.price) * item.quantity
            total += item_total
            items.append({
                'cart_item': item,
                'product': product,
                'total': item_total
            })

    return render_template('cart/view_cart.html', items=items, total=total)


@app.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        product_type = data.get('product_type')

        if product_type == 'wildlife':
            product = Wildlife.query.get(product_id)
        else:
            product = Safari.query.get(product_id)

        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

        cart_item = CartItem.query.filter_by(
            user_id=current_user.id,
            product_id=product_id,
            product_type=product_type
        ).first()

        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(
                user_id=current_user.id,
                product_id=product_id,
                product_type=product_type,
                quantity=1
            )
            db.session.add(cart_item)

        db.session.commit()

        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()

        return jsonify({
            'success': True,
            'message': 'Added to cart',
            'cart_count': cart_count
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    cart_item = CartItem.query.get_or_404(item_id)

    if cart_item.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('view_cart'))

    action = request.form.get('action')

    if action == 'increase':
        cart_item.quantity += 1
    elif action == 'decrease' and cart_item.quantity > 1:
        cart_item.quantity -= 1
    elif action == 'remove':
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart', 'info')
        return redirect(url_for('view_cart'))

    db.session.commit()
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('view_cart'))

    total = 0
    items = []

    for item in cart_items:
        if item.product_type == 'wildlife':
            product = Wildlife.query.get(item.product_id)
        else:
            product = Safari.query.get(item.product_id)

        if product:
            item_total = float(product.price) * item.quantity
            total += item_total
            items.append({
                'cart_item': item,
                'product': product,
                'total': item_total
            })

    if request.method == 'POST':
        order = Order(
            user_id=current_user.id,
            total_amount=total,
            payment_status='pending',
            shipping_address=request.form.get('address'),
            shipping_city=request.form.get('city'),
            shipping_state=request.form.get('state'),
            shipping_pincode=request.form.get('pincode')
        )
        db.session.add(order)
        db.session.commit()

        for item in cart_items:
            if item.product_type == 'wildlife':
                product = Wildlife.query.get(item.product_id)
            else:
                product = Safari.query.get(item.product_id)

            order_item = OrderItem(
                order_id=order.id,
                product_type=item.product_type,
                product_id=item.product_id,
                quantity=item.quantity,
                price=product.price if product else 0
            )
            db.session.add(order_item)

        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        session['order_id'] = order.id
        return redirect(url_for('order_summary'))

    return render_template('cart/checkout.html', items=items, total=total)

#----------order summary inserted
@app.route('/my-orders')
@login_required
def my_orders():
    """Display all orders for the current user"""
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()

    # Get order items for each order
    orders_with_items = []
    for order in orders:
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        items = []
        for item in order_items:
            if item.product_type == 'wildlife':
                product = Wildlife.query.get(item.product_id)
            else:
                product = Safari.query.get(item.product_id)
            items.append({
                'order_item': item,
                'product': product
            })
        orders_with_items.append({
            'order': order,
            'items': items
        })

    return render_template('profile/orders.html', orders=orders_with_items)
#------------ end---------------
@app.route('/order/summary')
@login_required
def order_summary():
    order_id = session.get('order_id')
    if not order_id:
        flash('No order found', 'warning')
        return redirect(url_for('index'))

    order = Order.query.get(order_id)
    if not order or order.user_id != current_user.id:
        flash('Order not found', 'danger')
        return redirect(url_for('index'))

    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    items = []

    for item in order_items:
        if item.product_type == 'wildlife':
            product = Wildlife.query.get(item.product_id)
        else:
            product = Safari.query.get(item.product_id)

        items.append({
            'order_item': item,
            'product': product
        })

    return render_template('cart/order_summary.html', order=order, items=items)


@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    stats = {
        'total_wildlife': Wildlife.query.count(),
        'total_safaris': Safari.query.count(),
        'total_orders': Order.query.count(),
        'total_users': User.query.count(),
        'recent_orders': Order.query.order_by(Order.created_at.desc()).limit(5).all()
    }
    # Pass current date to template
    current_date = datetime.now()

    return render_template('admin/dashboard.html', stats=stats, date=current_date)


@app.route('/admin/wildlife')
@login_required
def manage_wildlife():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    wildlife = Wildlife.query.all()
    return render_template('admin/manage_wildlife.html', wildlife=wildlife)


@app.route('/admin/wildlife/add', methods=['GET', 'POST'])
@login_required
def add_wildlife():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            file = request.files['image']
            filename = None
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

            wildlife = Wildlife(
                title=request.form['title'],
                description=request.form['description'],
                image_url=filename or 'default-wildlife.jpg',
                category=request.form['category'],
                price=float(request.form['price']),
                location=request.form.get('location', ''),
                status=request.form.get('status', 'Available')
            )

            db.session.add(wildlife)
            db.session.commit()
            flash('Wildlife added successfully', 'success')
            return redirect(url_for('manage_wildlife'))

        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    return render_template('admin/add_wildlife.html')


@app.route('/admin/wildlife/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_wildlife(id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    wildlife = Wildlife.query.get_or_404(id)

    if request.method == 'POST':
        try:
            wildlife.title = request.form['title']
            wildlife.description = request.form['description']
            wildlife.category = request.form['category']
            wildlife.price = float(request.form['price'])
            wildlife.location = request.form.get('location', '')
            wildlife.status = request.form.get('status', 'Available')

            file = request.files.get('image')
            if file and file.filename != '':
                if wildlife.image_url and wildlife.image_url != 'default-wildlife.jpg':
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], wildlife.image_url)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                wildlife.image_url = filename

            db.session.commit()
            flash('Wildlife updated successfully', 'success')
            return redirect(url_for('manage_wildlife'))

        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    return render_template('admin/edit_wildlife.html', wildlife=wildlife)
#-----------------------------safari
@app.route('/admin/safaris')
@login_required
def manage_safaris():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    safaris = Safari.query.all()
    return render_template('admin/manage_safaris.html', safaris=safaris)


@app.route('/admin/orders')
@login_required
def view_orders():
    """Admin view all orders"""
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    # Get all orders with user information
    orders = Order.query.order_by(Order.created_at.desc()).all()

    # Get order details for each order
    orders_with_details = []
    for order in orders:
        user = User.query.get(order.user_id)
        order_items = OrderItem.query.filter_by(order_id=order.id).all()

        items = []
        for item in order_items:
            if item.product_type == 'wildlife':
                product = Wildlife.query.get(item.product_id)
            else:
                product = Safari.query.get(item.product_id)

            items.append({
                'order_item': item,
                'product': product
            })

        orders_with_details.append({
            'order': order,
            'user': user,
            'items': items
        })

    return render_template('admin/view_orders.html', orders=orders_with_details)


@app.route('/admin/safari/add', methods=['GET', 'POST'])
@login_required
def add_safari():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Handle file upload
            file = request.files.get('image')
            filename = None
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

            # Create safari entry
            safari = Safari(
                name=request.form['name'],
                description=request.form.get('description', ''),
                price=float(request.form['price']),
                duration=request.form['duration'],
                safari_count=int(request.form['safari_count']),
                tier=request.form['tier'],
                image_url=filename or 'default-safari.jpg'
            )

            db.session.add(safari)
            db.session.commit()
            flash('Safari added successfully', 'success')
            return redirect(url_for('manage_safaris'))

        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    # For GET request, you need to create admin/add_safari.html
    # For now, redirect to manage_safaris
    return redirect(url_for('manage_safaris'))


# Add this function to get similar wildlife in wildlife_detail route
def get_similar_wildlife(category, exclude_id, limit=3):
    return Wildlife.query.filter(
        Wildlife.category == category,
        Wildlife.id != exclude_id
    ).limit(limit).all()
#-----------------------------end
#---------------------------start(safari detail)
@app.route('/safari/<int:id>')
def safari_detail(id):
    """Safari package detail page"""
    safari = Safari.query.get_or_404(id)

    # Get similar safaris (same tier)
    similar_safaris = Safari.query.filter(
        Safari.tier == safari.tier,
        Safari.id != safari.id
    ).limit(3).all()

    # Pass today's date for the booking form
    today = datetime.now().strftime('%Y-%m-%d')

    return render_template('safari/detail.html',
                           safari=safari,
                           similar_safaris=similar_safaris,
                           today=today)
#----------------------------end(safari detail)

@app.route('/admin/wildlife/delete/<int:id>', methods=['POST'])
@login_required
def delete_wildlife(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    wildlife = Wildlife.query.get_or_404(id)

    if wildlife.image_url and wildlife.image_url != 'default-wildlife.jpg':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], wildlife.image_url)
        if os.path.exists(filepath):
            os.remove(filepath)

    db.session.delete(wildlife)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Wildlife deleted successfully'})


@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', orders=orders)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


def create_sample_data():
    # Create admin user
    if not User.query.filter_by(email='admin@wildlife.com').first():
        admin = User(
            email='admin@wildlife.com',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)

    # Create sample wildlife
    if Wildlife.query.count() == 0:
        sample_wildlife = [
            Wildlife(
                title='Snow Leopard',
                description='The snow leopard, found in India\'s Himalayas, is an elusive big cat with thick fur and a long tail, perfectly adapted to cold, rocky terrains.',
                image_url='snow-leopard.jpg',
                category='Big Cats',
                price=2999.99,
                location='Himalayas'
            ),
            Wildlife(
                title='Himalayan Brown Bear',
                description='The brown bear, found in the Himalayan and northern regions of India, is a large, powerful mammal with thick fur, adapted to rugged terrains and cold climates.',
                image_url='brown-bear.jpg',
                category='Bears',
                price=2499.99,
                location='Himalayas'
            ),
            Wildlife(
                title='Gee\'s Golden Langur',
                description='Gee\'s golden langur, native to the forests of Assam in India and Bhutan, is known for its striking golden fur. This rare and endangered primate resides in high canopies.',
                image_url='golden-langur.jpg',
                category='Primates',
                price=1999.99,
                location='Assam'
            )
        ]

        for animal in sample_wildlife:
            db.session.add(animal)

    # Create sample safaris
    if Safari.query.count() == 0:
        sample_safaris = [
            Safari(
                name='Wildlife pitstop - Kanha',
                description='Experience the majestic tigers of Kanha National Park',
                price=20110,
                duration='1 Nights, 2 Days',
                safari_count=1,
                tier='Premium',
                image_url='kanha-safari.jpg'
            ),
            Safari(
                name='02 Safaris with 1N stay - Corbett',
                description='Thrilling jungle safari at Jim Corbett National Park',
                price=7100,
                duration='1 Nights, 2 Days',
                safari_count=2,
                tier='Economical',
                image_url='corbett-safari.jpg'
            ),
            Safari(
                name='Kuno Weekend Safari Getaway',
                description='Weekend adventure at Kuno National Park',
                price=22000,
                duration='1 Nights, 2 Days',
                safari_count=2,
                tier='Standard',
                image_url='kuno-safari.jpg'
            )
        ]

        for safari in sample_safaris:
            db.session.add(safari)

    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
    app.run(debug=False)