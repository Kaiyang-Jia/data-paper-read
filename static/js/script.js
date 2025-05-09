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
    // --- 修改：获取 Subject 筛选容器 ---
    const subjectFilterContainer = document.getElementById('subjectFilter'); // 假设 HTML 中容器 ID 改为 subjectFilter
    const pagination = document.getElementById('pagination');
    
    // --- 搜索相关元素 ---
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    
    // 全局变量
    let allArticles = [];
    // --- 修改：当前筛选条件改为 Subject ---
    let currentSubject = '全部'; 
    let currentPage = 1;
    let currentKeyword = ''; // 新增：当前搜索关键词
    const articlesPerPage = 10;  // 增加每页显示的文章数量，因为按日期分组后可能会导致每页实际文章数减少

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
    
    // --- 搜索功能：添加事件监听器 ---
    if (searchButton) {
        searchButton.addEventListener('click', handleSearch);
    }
    
    if (searchInput) {
        // 按回车键触发搜索
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
        
        // 输入框清空时，重置搜索
        searchInput.addEventListener('input', function() {
            if (this.value === '' && currentKeyword !== '') {
                currentKeyword = '';
                loadArticlesData();
            }
        });
    }
    
    // 处理搜索
    function handleSearch() {
        const keyword = searchInput.value.trim();
        if (keyword !== '') {
            currentKeyword = keyword;
            currentPage = 1; // 重置到第一页
            currentSubject = '全部'; // 重置分类筛选
            
            // 更新分类筛选标签的活跃状态
            if (subjectFilterContainer) {
                const pills = subjectFilterContainer.querySelectorAll('.tag-pill');
                pills.forEach(pill => {
                    if (pill.dataset.subject === '全部' || pill.dataset.tag === '全部') {
                        pill.classList.add('active');
                    } else {
                        pill.classList.remove('active');
                    }
                });
            }
            
            // 加载搜索结果
            loadArticlesData(true);
        }
    }
    
    // 加载文章数据
    function loadArticlesData(isSearch = false) {
        showLoading(true);
        
        // 构建查询参数
        let url = '/articles';
        const params = new URLSearchParams();
        
        if (currentSubject && currentSubject !== '全部') {
            params.append('subject', currentSubject);
        }
        
        if (isSearch && currentKeyword) {
            params.append('keyword', currentKeyword);
        }
        
        // 如果有参数，添加到URL
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                showLoading(false);
                
                allArticles = data || [];
                
                // 确保文章有正确的日期格式
                allArticles = allArticles.map(article => {
                    const publishDate = article.date || article.publishDate || '';
                    return {
                        ...article,
                        publishDate: publishDate,
                        // 标准化日期格式，用于排序和分组
                        normalizedDate: standardizeDate(publishDate)
                    };
                });
                
                // 按日期降序排序（最新的在前）
                allArticles.sort((a, b) => {
                    if (!a.normalizedDate) return 1;
                    if (!b.normalizedDate) return -1;
                    return new Date(b.normalizedDate) - new Date(a.normalizedDate);
                });
                
                // --- 修改：生成 Subject 筛选器 ---
                if (!isSearch || !currentKeyword) {
                    generateSubjectFilters(allArticles);
                }
                
                // 渲染文章
                renderArticles(currentPage);
                
                // 生成分页
                generatePagination();
                
                // 显示搜索结果状态
                if (isSearch && currentKeyword) {
                    showMessage(`找到 ${allArticles.length} 条与 "${currentKeyword}" 相关的结果`, 'info');
                }
            })
            .catch(error => {
                console.error('获取数据失败:', error);
                showLoading(false);
                showMessage('获取数据失败，请稍后再试或点击"刷新数据"按钮', 'danger');
            });
    }
    
    // 标准化日期格式函数
    function standardizeDate(dateStr) {
        if (!dateStr) return '';
        
        // 尝试解析日期
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            // 如果解析失败，尝试其他格式
            const formats = [
                /(\d{4})[/-](\d{1,2})[/-](\d{1,2})/, // YYYY-MM-DD 或 YYYY/MM/DD
                /(\d{1,2})[/-](\d{1,2})[/-](\d{4})/  // DD-MM-YYYY 或 DD/MM/YYYY
            ];
            
            for (const format of formats) {
                const match = dateStr.match(format);
                if (match) {
                    // 根据格式构造日期
                    if (format === formats[0]) {
                        return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
                    } else {
                        return `${match[3]}-${match[2].padStart(2, '0')}-${match[1].padStart(2, '0')}`;
                    }
                }
            }
            return '';
        }
        
        // 返回标准格式 YYYY-MM-DD
        return date.toISOString().split('T')[0];
    }
    
    // 格式化日期显示
    function formatDateForDisplay(dateStr) {
        if (!dateStr) return '未知日期';
        
        const normalizedDate = standardizeDate(dateStr);
        if (!normalizedDate) return dateStr; // 如果无法标准化，返回原始字符串
        
        const [year, month, day] = normalizedDate.split('-');
        return `${year}/${month}/${day}`;
    }

    // --- 修改：生成 Subject 筛选器 ---
    function generateSubjectFilters(articles) {
        if (!subjectFilterContainer) return;
        
        // 保留"全部"按钮
        const allSubjectElement = subjectFilterContainer.querySelector('[data-subject="全部"]');
        subjectFilterContainer.innerHTML = ''; // 清空现有按钮
        if (allSubjectElement) {
            subjectFilterContainer.appendChild(allSubjectElement);
        } else {
            const allSubjectBtn = document.createElement('div');
            allSubjectBtn.className = 'tag-pill active'; // 复用样式
            allSubjectBtn.dataset.subject = '全部';
            allSubjectBtn.textContent = '全部';
            subjectFilterContainer.appendChild(allSubjectBtn);
        }
        
        // 提取所有唯一的 Subject
        const uniqueSubjects = new Set();
        articles.forEach(article => {
            if (article.Subject && article.Subject.trim()) { // 检查 Subject 字段
                uniqueSubjects.add(article.Subject.trim());
            }
        });
        
        // 创建 Subject 按钮
        Array.from(uniqueSubjects).sort().forEach(subject => {
            const subjectElement = document.createElement('div');
            subjectElement.className = 'tag-pill'; // 复用样式
            subjectElement.dataset.subject = subject;
            subjectElement.textContent = subject;
            subjectFilterContainer.appendChild(subjectElement);
        });
        
        // 添加 Subject 按钮点击事件
        const subjectPills = subjectFilterContainer.querySelectorAll('.tag-pill');
        subjectPills.forEach(pill => {
            pill.addEventListener('click', () => {
                subjectPills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                currentSubject = pill.dataset.subject; // 更新当前 Subject
                currentPage = 1; // 重置到第一页
                renderArticles(currentPage);
                generatePagination();
            });
        });
    }

    // --- 修改：根据 Subject 筛选文章 ---
    function filterArticlesBySubject(articles, subject) {
        if (!subject || subject === '全部') {
            return articles; // 返回全部文章
        }
        
        return articles.filter(article => {
            // 直接比较 Subject 字段
            return article.Subject && article.Subject.trim() === subject.trim(); 
        });
    }

    // 渲染文章列表
    function renderArticles(page) {
        if (!articlesList) return;
        
        // --- 修改：按 Subject 筛选 ---
        const filteredArticles = filterArticlesBySubject(allArticles, currentSubject);
        
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
                    <p>在 "${currentSubject}" 分类下没有找到相关文章</p>
                    ${currentSubject !== '全部' ? '<p>请尝试选择其他分类或查看"全部"</p>' : ''}
                </div>
            `;
            return;
        }
        
        // 按日期分组文章
        const articlesByDate = {};
        paginatedArticles.forEach(article => {
            const dateStr = article.normalizedDate || '未知日期';
            if (!articlesByDate[dateStr]) {
                articlesByDate[dateStr] = [];
            }
            articlesByDate[dateStr].push(article);
        });
        
        // 按日期降序排列日期
        const sortedDates = Object.keys(articlesByDate).sort((a, b) => {
            if (a === '未知日期') return 1;
            if (b === '未知日期') return -1;
            return new Date(b) - new Date(a);
        });
        
        // 在每个日期组内，按更新时间排序
        for (const dateStr in articlesByDate) {
            articlesByDate[dateStr].sort((a, b) => {
                // 使用 updatedAt 字段作为更新时间，如果不存在则回退到其他时间字段
                const updateTimeA = a.updatedAt ? new Date(a.updatedAt) : 
                                  (a.updated ? new Date(a.updated) : new Date(a.normalizedDate));
                const updateTimeB = b.updatedAt ? new Date(b.updatedAt) : 
                                  (b.updated ? new Date(b.updated) : new Date(b.normalizedDate));
                
                // 降序排列，更新时间晚的排在前面
                return updateTimeB - updateTimeA;
            });
        }
        
        // 生成文章卡片，按日期分组
        sortedDates.forEach(dateStr => {
            // 添加日期分隔标题
            const dateHeader = document.createElement('div');
            dateHeader.className = 'date-separator';
            dateHeader.innerHTML = `<h3>${formatDateForDisplay(dateStr)}</h3>`;
            articlesList.appendChild(dateHeader);
            
            // 添加该日期下的所有文章
            const articlesContainer = document.createElement('div');
            articlesContainer.className = 'date-articles-group';
            
            articlesByDate[dateStr].forEach(article => {
                // 处理标签 (逻辑不变)
                let tagsHTML = '';
                if (article.tags) {
                    const tagsArray = Array.isArray(article.tags) ? article.tags : article.tags.split(',');
                    tagsHTML = tagsArray.map(tag => 
                        `<span class="paper-tag">${tag.trim()}</span>`
                    ).join('');
                }

                // --- 新增：处理 Subject ---
                const subjectHTML = article.Subject ? `<span class="paper-subject">分类: ${article.Subject}</span>` : '';
                
                // --- 新增：处理期刊信息 ---
                const journalHTML = article.journal ? `<span class="meta-item journal-badge">${article.journal}</span>` : '';
                
                const card = document.createElement('div');
                card.className = 'paper-card';
                
                card.innerHTML = `
                    <div class="paper-header">
                        <div class="paper-content">
                            <h3 class="paper-title">${article.title}</h3>
                            <p class="paper-cn-title">【${article.titleCn || article.title}】</p>
                            <div class="paper-meta">
                                ${journalHTML}
                                ${article.doi ? `<span class="meta-item doi-badge">DOI: ${article.doi}</span>` : ''}
                                <!-- 显示 Subject -->
                                ${subjectHTML ? `<span class="meta-item paper-subject-meta">${subjectHTML}</span>` : ''} 
                            </div>
                            <p class="paper-abstract">${article.interpretationCn || article.abstract || '暂无解读或摘要'}</p> 
                            <div class="paper-footer">
                                <div class="paper-tags">
                                    <!-- 显示标签 -->
                                    ${tagsHTML}
                                </div>
                                <div class="paper-actions">
                                    <a href="${article.url}" class="paper-link" target="_blank">查看原文</a>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                articlesContainer.appendChild(card);
            });
            
            articlesList.appendChild(articlesContainer);
        });
    }

    // 生成分页
    function generatePagination() {
        if (!pagination) return;
        
        // --- 修改：基于 Subject 筛选结果计算分页 ---
        const filteredArticles = filterArticlesBySubject(allArticles, currentSubject);
        const totalPages = Math.ceil(filteredArticles.length / articlesPerPage);
        
        pagination.innerHTML = '';
        
        // 如果只有一页，不显示分页
        if (totalPages <= 1) return;
        
        // 优化分页显示，只显示部分页码
        const maxVisiblePages = 5; // 最多显示的页码数量
        
        // 添加页码创建函数
        const createPageItem = (pageNum, isActive = false, text = pageNum) => {
            const pageItem = document.createElement('div');
            pageItem.className = `page-item ${isActive ? 'active' : ''}`;
            pageItem.textContent = text;
            
            if (pageNum > 0 && pageNum <= totalPages) {
                pageItem.addEventListener('click', () => {
                    currentPage = pageNum;
                    renderArticles(currentPage);
                    generatePagination();
                });
            } else {
                pageItem.classList.add('disabled');
            }
            
            return pageItem;
        };
        
        // 添加首页按钮
        if (totalPages > maxVisiblePages) {
            pagination.appendChild(createPageItem(1, currentPage === 1));
        }
        
        // 计算要显示的页码范围
        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
        
        // 调整起始页，确保显示完整的页码数
        if (endPage - startPage + 1 < maxVisiblePages) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }
        
        // 如果首页和起始页之间有间隔，添加省略号
        if (startPage > 2) {
            pagination.appendChild(createPageItem(0, false, '...'));
        }
        
        // 添加中间的页码
        for (let i = startPage; i <= endPage; i++) {
            if (i !== 1 && i !== totalPages) { // 避免重复添加首页和尾页
                pagination.appendChild(createPageItem(i, i === currentPage));
            }
        }
        
        // 如果尾页和结束页之间有间隔，添加省略号
        if (endPage < totalPages - 1) {
            pagination.appendChild(createPageItem(0, false, '...'));
        }
        
        // 添加尾页按钮
        if (totalPages > maxVisiblePages) {
            pagination.appendChild(createPageItem(totalPages, currentPage === totalPages));
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