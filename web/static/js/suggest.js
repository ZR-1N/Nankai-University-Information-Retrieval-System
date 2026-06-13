/**
 * 搜索联想推荐 - 前端 JS
 * 当用户在搜索框中输入时，通过 AJAX 获取推荐查询词
 */

(function () {
    'use strict';

    // 搜索联想状态
    let suggestTimeout = null;
    let activeIndex = -1;

    /**
     * 初始化搜索联想
     * @param {string} inputId - 搜索框元素 ID
     * @param {string} dropdownId - 下拉框元素 ID
     */
    function initSuggest(inputId, dropdownId) {
        const input = document.getElementById(inputId);
        const dropdown = document.getElementById(dropdownId);

        if (!input || !dropdown) return;

        // 输入事件
        input.addEventListener('input', function () {
            clearTimeout(suggestTimeout);
            const query = this.value.trim();

            if (query.length === 0) {
                hideSuggest(dropdown);
                return;
            }

            if (query.length < 1) {
                hideSuggest(dropdown);
                return;
            }

            // 防抖：300ms 后请求
            suggestTimeout = setTimeout(function () {
                fetchSuggestions(query, dropdown, input);
            }, 300);
        });

        // 键盘导航
        input.addEventListener('keydown', function (e) {
            const items = dropdown.querySelectorAll('.suggest-item');

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                updateActiveItem(items, dropdown);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = Math.max(activeIndex - 1, -1);
                updateActiveItem(items, dropdown);
            } else if (e.key === 'Enter') {
                if (activeIndex >= 0 && items.length > 0) {
                    e.preventDefault();
                    const activeItem = items[activeIndex];
                    input.value = activeItem.getAttribute('data-text') || activeItem.textContent.trim();
                    hideSuggest(dropdown);
                    input.form.submit();
                }
            } else if (e.key === 'Escape') {
                hideSuggest(dropdown);
            }
        });

        // 点击外部关闭
        document.addEventListener('click', function (e) {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                hideSuggest(dropdown);
            }
        });
    }

    /**
     * 获取搜索建议
     */
    function fetchSuggestions(query, dropdown, input) {
        // 获取用户 ID
        const userSelect = document.querySelector('select[name="user_id"]');
        const userId = userSelect ? userSelect.value : 'default';

        fetch('/api/suggest?q=' + encodeURIComponent(query) + '&user_id=' + encodeURIComponent(userId))
            .then(function (response) {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            })
            .then(function (data) {
                if (!data || data.length === 0) {
                    hideSuggest(dropdown);
                    return;
                }
                renderSuggestions(data, dropdown, input);
            })
            .catch(function () {
                hideSuggest(dropdown);
            });
    }

    /**
     * 渲染搜索建议
     */
    function renderSuggestions(suggestions, dropdown, input) {
        dropdown.innerHTML = '';
        activeIndex = -1;

        suggestions.forEach(function (item) {
            const div = document.createElement('div');
            div.className = 'suggest-item';
            div.setAttribute('data-text', item.text);

            const icon = document.createElement('i');
            if (item.type === 'history') {
                icon.className = 'bi bi-clock-history text-muted';
            } else if (item.type === 'hot') {
                icon.className = 'bi bi-fire text-danger';
            } else {
                icon.className = 'bi bi-file-text text-primary';
            }
            div.appendChild(icon);

            const textSpan = document.createElement('span');
            textSpan.textContent = item.text;
            textSpan.style.flex = '1';
            div.appendChild(textSpan);

            const typeBadge = document.createElement('span');
            typeBadge.className = 'suggest-type';
            if (item.type === 'history') {
                typeBadge.textContent = '历史';
            } else if (item.type === 'hot') {
                typeBadge.textContent = '热门';
            } else {
                typeBadge.textContent = '标题';
            }
            div.appendChild(typeBadge);

            // 点击事件
            div.addEventListener('click', function () {
                input.value = item.text;
                hideSuggest(dropdown);
                input.form.submit();
            });

            dropdown.appendChild(div);
        });

        dropdown.style.display = 'block';
    }

    /**
     * 更新键盘高亮项
     */
    function updateActiveItem(items, dropdown) {
        items.forEach(function (item, index) {
            if (index === activeIndex) {
                item.classList.add('active');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('active');
            }
        });
    }

    /**
     * 隐藏下拉框
     */
    function hideSuggest(dropdown) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        activeIndex = -1;
    }

    // 在 DOM 加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            // 首页搜索框
            initSuggest('search-input', 'suggest-dropdown');
            // 结果页搜索框
            initSuggest('search-input-inline', 'suggest-dropdown-inline');
        });
    } else {
        initSuggest('search-input', 'suggest-dropdown');
        initSuggest('search-input-inline', 'suggest-dropdown-inline');
    }
})();
