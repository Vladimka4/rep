// Добавление в корзину
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для кнопок "Добавить в корзину"
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
                    const cartCount = document.querySelector('#cart-count');
                    if (cartCount) {
                        cartCount.textContent = data.cart_total;
                    }
                    
                    // Показываем уведомление
                    showAlert(data.message, 'success');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Ошибка при добавлении в корзину', 'danger');
            });
        });
    });
    
    // Обновление количества в корзине
    const quantityInputs = document.querySelectorAll('.quantity-input');
    
    quantityInputs.forEach(input => {
        input.addEventListener('change', function() {
            const dishId = this.dataset.dishId;
            const quantity = this.value;
            
            fetch(`/update_cart/${dishId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify({ quantity: quantity })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            });
        });
    });
    
    // Удаление из корзины
    const removeButtons = document.querySelectorAll('.remove-from-cart');
    
    removeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const dishId = this.dataset.dishId;
            
            if (confirm('Удалить товар из корзины?')) {
                fetch(`/remove_from_cart/${dishId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    }
                });
            }
        });
    });
});

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