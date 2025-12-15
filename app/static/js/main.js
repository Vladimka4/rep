// Функция показа уведомления
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.parentNode.removeChild(alertDiv);
        }
    }, 3000);
}

// Добавление в корзину с главной страницы
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для кнопок "Добавить в корзину" на главной
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function() {
            const dishId = this.dataset.dishId;
            
            fetch(`/add_to_cart/${dishId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Обновляем счетчик корзины
                    updateCartCount(data.cart_total);
                    showAlert(data.message, 'success');
                } else {
                    showAlert(data.message, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Ошибка при добавлении в корзину', 'danger');
            });
        });
    });
    
    // Функция обновления счетчика корзины
    function updateCartCount(count) {
        const cartCount = document.querySelector('#cart-count');
        const cartBtn = document.querySelector('a[href="/cart"]');
        
        if (cartCount) {
            cartCount.textContent = count;
        } else if (cartBtn && count > 0) {
            const badge = document.createElement('span');
            badge.id = 'cart-count';
            badge.className = 'position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger';
            badge.textContent = count;
            cartBtn.appendChild(badge);
        }
        
        // Если корзина пуста, удаляем бейдж
        if (count === 0 && cartCount) {
            cartCount.remove();
        }
    }
});