// Admin Panel JavaScript

let allUsers = [];
let filteredUsers = [];

// Load data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    
    // Set up event listeners
    document.getElementById('search-input').addEventListener('input', filterUsers);
    document.getElementById('filter-premium').addEventListener('change', filterUsers);
});

// Load all data
async function loadData() {
    await Promise.all([
        loadStatistics(),
        loadUsers()
    ]);
}

// Load global statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/statistics');
        const stats = await response.json();
        
        document.getElementById('total-users').textContent = stats.total_users;
        document.getElementById('premium-users').textContent = stats.premium_users;
        document.getElementById('sentences-today').textContent = stats.sentences_today;
        document.getElementById('active-users').textContent = stats.active_users_7d;
    } catch (error) {
        console.error('Error loading statistics:', error);
        showError('Ошибка загрузки статистики');
    }
}

// Load users
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        
        allUsers = data.users;
        filteredUsers = allUsers;
        renderUsers();
    } catch (error) {
        console.error('Error loading users:', error);
        showError('Ошибка загрузки пользователей');
    }
}

// Render users table
function renderUsers() {
    const tbody = document.getElementById('users-tbody');
    
    if (filteredUsers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" class="loading-cell">
                    Пользователи не найдены
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filteredUsers.map(user => `
        <tr>
            <td><strong>${user.telegram_id}</strong></td>
            <td>${escapeHtml(user.first_name)}</td>
            <td>@${escapeHtml(user.username)}</td>
            <td>
                <span class="premium-badge ${user.is_premium ? 'premium' : 'regular'}">
                    ${user.is_premium ? '⭐ Premium' : '👤 Regular'}
                </span>
            </td>
            <td>
                ${user.is_premium 
                    ? '<span style="color: var(--accent-gold);">∞ Безлимит</span>' 
                    : `${user.daily_generation_count} / 3`
                }
            </td>
            <td>${user.total_sentences}</td>
            <td>${user.recent_sentences_7d}</td>
            <td>
                <span style="color: ${getDifficultyColor(user.difficulty_level)};">
                    ${'⭐'.repeat(user.difficulty_level)}
                </span>
            </td>
            <td>${formatDate(user.created_at)}</td>
            <td>
                <button 
                    class="toggle-btn" 
                    onclick="togglePremium(${user.telegram_id}, ${!user.is_premium})"
                >
                    ${user.is_premium ? '❌ Убрать Premium' : '⭐ Дать Premium'}
                </button>
            </td>
        </tr>
    `).join('');
}

// Filter users
function filterUsers() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const premiumFilter = document.getElementById('filter-premium').value;
    
    filteredUsers = allUsers.filter(user => {
        // Search filter
        const matchesSearch = 
            user.telegram_id.toString().includes(searchTerm) ||
            user.first_name.toLowerCase().includes(searchTerm) ||
            user.username.toLowerCase().includes(searchTerm);
        
        // Premium filter
        const matchesPremium = 
            premiumFilter === 'all' ||
            (premiumFilter === 'premium' && user.is_premium) ||
            (premiumFilter === 'regular' && !user.is_premium);
        
        return matchesSearch && matchesPremium;
    });
    
    renderUsers();
}

// Toggle premium status
async function togglePremium(telegramId, isPremium) {
    try {
        const response = await fetch('/api/users/premium', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                telegram_id: telegramId,
                is_premium: isPremium
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to toggle premium');
        }
        
        const result = await response.json();
        
        // Update local data
        const user = allUsers.find(u => u.telegram_id === telegramId);
        if (user) {
            user.is_premium = isPremium;
        }
        
        // Re-render
        filterUsers();
        loadStatistics();
        
        // Show success message
        showSuccess(result.message);
    } catch (error) {
        console.error('Error toggling premium:', error);
        showError('Ошибка при изменении статуса');
    }
}

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function getDifficultyColor(level) {
    const colors = {
        1: 'var(--accent-green)',
        2: 'var(--accent-gold)',
        3: '#ef4444'
    };
    return colors[level] || 'var(--text-secondary)';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(message) {
    // Simple alert for now - can be replaced with a toast notification
    alert('✅ ' + message);
}

function showError(message) {
    alert('❌ ' + message);
}
