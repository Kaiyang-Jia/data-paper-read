/**
 * Nature数据期刊论文网页交互脚本
 */
document.addEventListener('DOMContentLoaded', function() {
    // DOM 元素引用
    const articlesList = document.getElementById('articlesList');
    const statusMessage = document.getElementById('statusMessage');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const modal = document.getElementById('articleDetailModal');
    const closeModalBtn = document.getElementById('closeModal');
    const closeSecondaryBtn = document.querySelector('.close-btn-secondary');
    const tagsFilter = document.getElementById('tagsFilter');
    const pagination = document.getElementById('pagination');
    
    // 全局变量
    let allArticles = [];
    let currentTag = '全部';
    let currentPage = 1;
    const articlesPerPage = 6;

    // 加载初始数据
    loadArticlesData();

    // 关闭模态框按钮
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    
    if (closeSecondaryBtn) {
        closeSecondaryBtn.addEventListener('click', closeModal);
    }
    
    // 点击模态框外部关闭模态框
    window.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // 加载文章数据
    function loadArticlesData() {
        showLoading(true);
        
        fetch('/articles')
            .then(response => response.json())
            .then(data => {
                showLoading(false);
                
                allArticles = data || [];
                
                // 生成唯一标签
                generateTagFilters(allArticles);
                
                // 渲染文章
                renderArticles(currentPage);
                
                // 生成分页
                generatePagination();
            })
            .catch(error => {
                console.error('获取数据失败:', error);
                showLoading(false);
                showMessage('获取数据失败，请稍后再试或点击"刷新数据"按钮', 'danger');
            });
    }

    // 生成标签筛选器
    function generateTagFilters(articles) {
        if (!tagsFilter) return;
        
        // 保留"全部"标签
        const allTagElement = tagsFilter.querySelector('[data-tag="全部"]');
        tagsFilter.innerHTML = '';
        if (allTagElement) {
            tagsFilter.appendChild(allTagElement);
        } else {
            const allTag = document.createElement('div');
            allTag.className = 'tag-pill active';
            allTag.dataset.tag = '全部';
            allTag.textContent = '全部';
            tagsFilter.appendChild(allTag);
        }
        
        // 提取所有唯一标签
        const uniqueTags = new Set();
        articles.forEach(article => {
            if (article.tags) {
                const tagsArray = Array.isArray(article.tags) ? article.tags : article.tags.split(',');
                tagsArray.forEach(tag => {
                    const trimmedTag = tag.trim();
                    if (trimmedTag) {
                        uniqueTags.add(trimmedTag);
                    }
                });
            }
        });
        
        // 创建标签元素
        Array.from(uniqueTags).sort().forEach(tag => {
            const tagElement = document.createElement('div');
            tagElement.className = 'tag-pill';
            tagElement.dataset.tag = tag;
            tagElement.textContent = tag;
            tagsFilter.appendChild(tagElement);
        });
        
        // 添加标签点击事件
        const tagPills = tagsFilter.querySelectorAll('.tag-pill');
        tagPills.forEach(pill => {
            pill.addEventListener('click', () => {
                tagPills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                currentTag = pill.dataset.tag;
                currentPage = 1;
                renderArticles(currentPage);
                generatePagination();
            });
        });
    }

    // 根据标签筛选文章
    function filterArticlesByTag(articles, tag) {
        if (!tag || tag === '全部') {
            return articles;
        }
        
        return articles.filter(article => {
            if (!article.tags) return false;
            
            // 确保tags是数组
            const tagsArray = Array.isArray(article.tags) ? article.tags : article.tags.split(',');
            return tagsArray.some(t => t.trim() === tag.trim());
        });
    }

    // 渲染文章列表
    function renderArticles(page) {
        if (!articlesList) return;
        
        // 筛选文章
        const filteredArticles = filterArticlesByTag(allArticles, currentTag);
        
        // 计算分页
        const start = (page - 1) * articlesPerPage;
        const end = start + articlesPerPage;
        const paginatedArticles = filteredArticles.slice(start, end);
        
        // 清空容器
        articlesList.innerHTML = '';
        
        // 无结果处理
        if (paginatedArticles.length === 0) {
            articlesList.innerHTML = `
                <div class="no-results">
                    <p>没有找到相关文章</p>
                    ${currentTag !== '全部' ? '<p>请尝试选择其他标签或查看"全部"分类</p>' : ''}
                </div>
            `;
            return;
        }
        
        // 生成文章卡片
        paginatedArticles.forEach((article, index) => {
            // 生成随机的投票数
            const voteCount = Math.floor(Math.random() * 100) + 50;
            
            // 处理标签
            let tagsHTML = '';
            if (article.tags) {
                const tagsArray = Array.isArray(article.tags) ? article.tags : article.tags.split(',');
                tagsHTML = tagsArray.map(tag => 
                    `<span class="paper-tag">${tag.trim()}</span>`
                ).join('');
            }
            
            const card = document.createElement('div');
            card.className = 'paper-card';
            
            card.innerHTML = `
                <div class="paper-header">
                    <div class="voting">
                        <span class="vote-icon">▲</span>
                        <span class="vote-count">${voteCount}</span>
                    </div>
                    <div class="paper-content">
                        <h3 class="paper-title">${article.title}</h3>
                        <p class="paper-cn-title">【${article.titleCn || article.title}】</p>
                        <div class="paper-meta">
                            <span class="meta-item">发布: ${article.date || article.publishDate || '未知日期'}</span>
                            ${article.doi ? `<span class="meta-item">DOI: ${article.doi}</span>` : ''}
                        </div>
                        <p class="paper-abstract">${article.abstract || article.interpretationCn || ''}</p>
                        <div class="paper-footer">
                            <div class="paper-tags">
                                ${tagsHTML}
                            </div>
                            <div class="paper-actions">
                                <a href="${article.url}" class="paper-link" target="_blank">查看原文</a>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            articlesList.appendChild(card);
        });
    }

    // 生成分页
    function generatePagination() {
        if (!pagination) return;
        
        const filteredArticles = filterArticlesByTag(allArticles, currentTag);
        const totalPages = Math.ceil(filteredArticles.length / articlesPerPage);
        
        pagination.innerHTML = '';
        
        // 如果只有一页，不显示分页
        if (totalPages <= 1) return;
        
        // 生成页码
        for (let i = 1; i <= totalPages; i++) {
            const pageItem = document.createElement('div');
            pageItem.className = `page-item ${i === currentPage ? 'active' : ''}`;
            pageItem.textContent = i;
            
            pageItem.addEventListener('click', () => {
                currentPage = i;
                renderArticles(currentPage);
                
                // 更新活动页
                const pageItems = pagination.querySelectorAll('.page-item');
                pageItems.forEach(item => {
                    item.classList.remove('active');
                });
                pageItem.classList.add('active');
            });
            
            pagination.appendChild(pageItem);
        }
    }

    // 显示文章详情
    function showArticleDetails(index) {
        const article = allArticles[index];
        if (!article || !modal) return;
        
        // 设置模态框内容
        document.getElementById('modalTitle').textContent = article.titleCn || article.title;
        document.getElementById('modalAuthors').textContent = article.authors || '未知作者';
        document.getElementById('modalDate').textContent = `发布日期: ${article.date || article.publishDate || '未知日期'}`;
        document.getElementById('modalAbstract').textContent = article.interpretationCn || article.abstract || '暂无摘要';
        
        // DOI
        const doiElement = document.getElementById('modalDoi');
        if (doiElement) {
            if (article.doi) {
                doiElement.querySelector('span').textContent = article.doi;
                doiElement.style.display = 'block';
            } else {
                doiElement.style.display = 'none';
            }
        }
        
        // 数据集链接
        const datasetsElement = document.getElementById('modalDatasets');
        if (datasetsElement) {
            const datasetsList = datasetsElement.querySelector('ul');
            datasetsList.innerHTML = '';
            
            if (article.dataset_links && article.dataset_links.length > 0) {
                article.dataset_links.forEach(link => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item';
                    const a = document.createElement('a');
                    a.href = link;
                    a.textContent = link;
                    a.target = '_blank';
                    li.appendChild(a);
                    datasetsList.appendChild(li);
                });
                datasetsElement.style.display = 'block';
            } else {
                datasetsList.innerHTML = '<li class="list-group-item">暂无相关数据集链接</li>';
                datasetsElement.style.display = 'block';
            }
        }
        
        // 原文链接
        const modalLink = document.getElementById('modalLink');
        if (modalLink) {
            modalLink.href = article.url || '#';
        }
        
        // 显示模态框
        modal.style.display = 'block';
    }

    // 关闭模态框
    function closeModal() {
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // 显示加载状态
    function showLoading(show) {
        if (loadingOverlay) {
            loadingOverlay.style.display = show ? 'flex' : 'none';
        }
    }

    // 显示消息
    function showMessage(message, type = 'info') {
        if (!statusMessage) return;
        
        statusMessage.textContent = message;
        statusMessage.className = `alert alert-${type}`;
        statusMessage.style.display = 'block';
        
        // 3秒后自动隐藏
        setTimeout(() => {
            statusMessage.style.display = 'none';
        }, 3000);
    }
});