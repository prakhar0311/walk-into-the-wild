// static/js/scripts.js - Main JavaScript file

// Global variables
let cartCount = 0;

// Document ready
$(document).ready(function() {
    initializeTooltips();
    initializeAlerts();
    loadCartCount();
    setupEventListeners();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    $('[data-bs-toggle="tooltip"]').tooltip();
}

// Setup event listeners
function setupEventListeners() {
    // Add to cart buttons
    $(document).on('click', '.add-to-cart', function(e) {
        e.preventDefault();
        const productId = $(this).data('id');
        const productType = $(this).data('type');
        addToCart(productId, productType);
    });

    // Quantity controls
    $(document).on('click', '.quantity-btn', function(e) {
        e.preventDefault();
        const action = $(this).hasClass('increase') ? 'increase' : 'decrease';
        const itemId = $(this).data('item-id');
        updateCartItem(itemId, action);
    });

    // Payment method selection
    $(document).on('click', '.payment-method', function() {
        $('.payment-method').removeClass('selected');
        $(this).addClass('selected');
    });

    // Image preview for file inputs
    $(document).on('change', '.image-upload', function(e) {
        const input = this;
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                $(input).siblings('.image-preview').attr('src', e.target.result).show();
            }
            reader.readAsDataURL(input.files[0]);
        }
    });
}

// Add item to cart
function addToCart(productId, productType) {
    if (!isLoggedIn()) {
        showAlert('Please login to add items to cart', 'warning', true);
        return;
    }

    $.ajax({
        url: '/cart/add',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            product_id: productId,
            product_type: productType
        }),
        beforeSend: function() {
            showLoader();
        },
        success: function(response) {
            if (response.success) {
                updateCartCount(response.cart_count);
                showAlert('Item added to cart successfully!', 'success');

                // Update button state
                $(`.add-to-cart[data-id="${productId}"][data-type="${productType}"]`)
                    .html('<i class="fas fa-check me-2"></i>Added')
                    .removeClass('btn-success')
                    .addClass('btn-secondary')
                    .prop('disabled', true);

                // Reset after 2 seconds
                setTimeout(() => {
                    $(`.add-to-cart[data-id="${productId}"][data-type="${productType}"]`)
                        .html('<i class="fas fa-cart-plus me-2"></i>Add to Cart')
                        .removeClass('btn-secondary')
                        .addClass('btn-success')
                        .prop('disabled', false);
                }, 2000);
            } else {
                showAlert(response.message || 'Error adding to cart', 'danger');
            }
        },
        error: function(xhr) {
            if (xhr.status === 401) {
                showAlert('Please login to add items to cart', 'warning', true);
            } else {
                showAlert('Error adding item to cart', 'danger');
            }
        },
        complete: function() {
            hideLoader();
        }
    });
}

// Update cart item quantity
function updateCartItem(itemId, action) {
    $.ajax({
        url: `/cart/update/${itemId}`,
        type: 'POST',
        data: { action: action },
        success: function(response) {
            location.reload(); // Reload to update totals
        },
        error: function() {
            showAlert('Error updating cart', 'danger');
        }
    });
}

// Remove item from cart
function removeCartItem(itemId) {
    if (confirm('Are you sure you want to remove this item?')) {
        $.ajax({
            url: `/cart/remove/${itemId}`,
            type: 'POST',
            success: function(response) {
                if (response.success) {
                    showAlert('Item removed from cart', 'success');
                    location.reload();
                }
            },
            error: function() {
                showAlert('Error removing item', 'danger');
            }
        });
    }
}

// Load cart count from server
function loadCartCount() {
    if (isLoggedIn()) {
        $.get('/cart/count', function(data) {
            if (data.success) {
                updateCartCount(data.count);
            }
        }).fail(function() {
            // If API fails, check cart page
            cartCount = parseInt($('#cartCount').text()) || 0;
        });
    }
}

// Update cart count display
function updateCartCount(count) {
    cartCount = count;
    $('#cartCount').text(count);

    // Add animation
    $('#cartCount').addClass('animate__animated animate__bounce');
    setTimeout(() => {
        $('#cartCount').removeClass('animate__animated animate__bounce');
    }, 1000);
}

// Check if user is logged in
function isLoggedIn() {
    return $('body').data('user-authenticated') === 'true';
}

// Show alert message
function showAlert(message, type, redirectToLogin = false) {
    // Remove existing alerts
    $('.alert-dismissible').remove();

    // Create alert
    const alertId = 'alert-' + Date.now();
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show"
             style="position: fixed; top: 80px; right: 20px; z-index: 9999; min-width: 300px;">
            ${message}
            ${redirectToLogin ? '<br><small>Click <a href="/login" class="alert-link">here</a> to login</small>' : ''}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    // Add to page
    $('body').append(alertHtml);

    // Auto remove after 5 seconds
    setTimeout(() => {
        $(`#${alertId}`).alert('close');
    }, 5000);
}

// Initialize alert system
function initializeAlerts() {
    // Auto-dismiss flash messages after 5 seconds
    setTimeout(() => {
        $('.alert:not(.alert-permanent)').alert('close');
    }, 5000);
}

// Show loading spinner
function showLoader(message = 'Loading...') {
    // Remove existing loader
    hideLoader();

    const loaderHtml = `
        <div id="global-loader" class="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
             style="background: rgba(0,0,0,0.5); z-index: 99999;">
            <div class="text-center">
                <div class="spinner-border text-success" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="text-white mt-3">${message}</div>
            </div>
        </div>
    `;

    $('body').append(loaderHtml);
}

// Hide loading spinner
function hideLoader() {
    $('#global-loader').remove();
}

// Image preview for admin uploads
function previewImage(input, previewId) {
    const preview = document.getElementById(previewId);
    const file = input.files[0];
    const reader = new FileReader();

    reader.onloadend = function() {
        preview.src = reader.result;
        preview.style.display = 'block';
    }

    if (file) {
        reader.readAsDataURL(file);
    } else {
        preview.src = '';
        preview.style.display = 'none';
    }
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form.checkValidity()) {
        form.classList.add('was-validated');
        return false;
    }
    return true;
}

// Confirm delete action
function confirmDelete(itemName, deleteUrl) {
    if (confirm(`Are you sure you want to delete "${itemName}"? This action cannot be undone.`)) {
        window.location.href = deleteUrl;
    }
    return false;
}

// Toggle password visibility
function togglePasswordVisibility(inputId, toggleButtonId) {
    const input = document.getElementById(inputId);
    const button = document.getElementById(toggleButtonId);

    if (input.type === 'password') {
        input.type = 'text';
        button.innerHTML = '<i class="fas fa-eye-slash"></i>';
    } else {
        input.type = 'password';
        button.innerHTML = '<i class="fas fa-eye"></i>';
    }
}

// Filter wildlife/safari items
function filterItems(category) {
    $('.item-card').hide();
    if (category === 'all') {
        $('.item-card').show();
    } else {
        $(`.item-card[data-category="${category}"]`).show();
    }

    // Update active filter button
    $('.filter-btn').removeClass('active');
    $(`.filter-btn[data-filter="${category}"]`).addClass('active');
}

// Search functionality
function searchItems(searchTerm) {
    const term = searchTerm.toLowerCase();
    $('.item-card').each(function() {
        const title = $(this).data('title').toLowerCase();
        const description = $(this).data('description').toLowerCase();

        if (title.includes(term) || description.includes(term)) {
            $(this).show();
        } else {
            $(this).hide();
        }
    });
}

// Smooth scroll to section
function scrollToSection(sectionId) {
    $('html, body').animate({
        scrollTop: $(sectionId).offset().top - 100
    }, 500);
}

// Initialize animations
function initAnimations() {
    // Animate on scroll
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 1000,
            once: true,
            offset: 100
        });
    }

    // Animate counter
    $('.counter').each(function() {
        $(this).prop('Counter', 0).animate({
            Counter: $(this).text()
        }, {
            duration: 2000,
            easing: 'swing',
            step: function(now) {
                $(this).text(Math.ceil(now));
            }
        });
    });
}

// Currency formatting
function formatCurrency(amount) {
    return '₹ ' + amount.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Date formatting
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Initialize when page loads
$(window).on('load', function() {
    initAnimations();

    // Check for URL parameters for messages
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('message')) {
        const message = urlParams.get('message');
        const type = urlParams.has('type') ? urlParams.get('type') : 'info';
        showAlert(decodeURIComponent(message), type);
    }
});