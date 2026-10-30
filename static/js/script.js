document.addEventListener("DOMContentLoaded", () => {
    const elements = {
        articlesList: document.getElementById("articlesList"),
        statusMessage: document.getElementById("statusMessage"),
        loadingOverlay: document.getElementById("loadingOverlay"),
        modal: document.getElementById("articleDetailModal"),
        closeModalButton: document.getElementById("closeModal"),
        closeSecondaryButton: document.querySelector(".close-btn-secondary"),
        subjectFilter: document.getElementById("subjectFilter"),
        journalFilter: document.getElementById("journalFilter"),
        dateFilter: document.getElementById("dateFilter"),
        sortFilter: document.getElementById("sortFilter"),
        resetFiltersButton: document.getElementById("resetFiltersButton"),
        activeFilters: document.getElementById("activeFilters"),
        pagination: document.getElementById("pagination"),
        searchInput: document.getElementById("searchInput"),
        searchButton: document.getElementById("searchButton"),
        clearSearchButton: document.getElementById("clearSearchButton"),
        resultSummary: document.getElementById("resultSummary"),
        assistantForm: document.getElementById("researchAssistantForm"),
        researchQuestion: document.getElementById("researchQuestion"),
        askAssistantButton: document.getElementById("askAssistantButton"),
        assistantResponse: document.getElementById("assistantResponse"),
        modalFavoriteButton: document.getElementById("modalFavoriteButton")
    };

    const isAuthenticated = document.body.dataset.authenticated === "true";
    const loginUrl = document.body.dataset.loginUrl || "/login";
    const state = {
        articles: [],
        favoriteKeys: new Set(),
        keyword: "",
        subject: "全部",
        journal: "全部",
        dateRange: "all",
        sort: "newest",
        page: 1
    };

    const articlesPerPage = 10;
    let searchTimer = null;
    let lastFocusedElement = null;
    let activeModalArticle = null;

    restoreStateFromUrl();
    bindStaticEvents();
    loadLibraryState();
    loadArticlesData();

    function bindStaticEvents() {
        elements.searchInput?.addEventListener("input", () => {
            elements.clearSearchButton.hidden = !elements.searchInput.value;
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => applySearch(false), 320);
        });

        elements.searchInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                window.clearTimeout(searchTimer);
                applySearch(true);
            }
        });

        elements.searchButton?.addEventListener("click", () => {
            window.clearTimeout(searchTimer);
            applySearch(true);
        });

        elements.clearSearchButton?.addEventListener("click", () => {
            elements.searchInput.value = "";
            elements.clearSearchButton.hidden = true;
            state.keyword = "";
            state.page = 1;
            applyState();
            elements.searchInput.focus();
        });

        elements.journalFilter?.addEventListener("change", () => {
            state.journal = elements.journalFilter.value;
            state.page = 1;
            applyState();
        });

        elements.dateFilter?.addEventListener("change", () => {
            state.dateRange = elements.dateFilter.value;
            state.page = 1;
            applyState();
        });

        elements.sortFilter?.addEventListener("change", () => {
            state.sort = elements.sortFilter.value;
            state.page = 1;
            applyState();
        });

        elements.resetFiltersButton?.addEventListener("click", resetFilters);
        elements.assistantForm?.addEventListener("submit", handleAssistantSubmit);
        document.querySelectorAll(".assistant-examples button").forEach((button) => {
            button.addEventListener("click", () => {
                elements.researchQuestion.value = button.dataset.question || "";
                elements.researchQuestion.focus();
            });
        });
        elements.closeModalButton?.addEventListener("click", closeModal);
        elements.closeSecondaryButton?.addEventListener("click", closeModal);
        elements.modalFavoriteButton?.addEventListener("click", () => {
            if (activeModalArticle) toggleFavorite(activeModalArticle, elements.modalFavoriteButton);
        });
        elements.modal?.addEventListener("click", (event) => {
            if (event.target === elements.modal) closeModal();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && elements.modal?.classList.contains("visible")) {
                closeModal();
            }
        });

        window.addEventListener("popstate", () => {
            restoreStateFromUrl();
            syncControls();
            applyState(false);
        });
    }

    function getArticleKey(article) {
        if (article.doi?.trim()) return `doi:${article.doi.trim().toLowerCase()}`;
        if (article.url?.trim()) return `url:${article.url.trim()}`;
        const title = (article.titleCn || article.title || "").trim().toLowerCase();
        return title ? `title:${title}` : "";
    }

    function getArticleSnapshot(article) {
        return {
            doi: article.doi || "",
            url: article.url || "",
            title: article.title || "",
            titleCn: article.titleCn || "",
            journal: article.journal || "",
            Subject: article.Subject || "",
            publishDate: article.publishDate || article.date || ""
        };
    }

    function loadLibraryState() {
        if (!isAuthenticated) return;
        fetch("/api/library/state")
            .then((response) => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then((data) => {
                state.favoriteKeys = new Set(data.favoriteKeys || []);
                syncFavoriteButtons();
            })
            .catch((error) => console.error("加载收藏状态失败:", error));
    }

    function requireLogin() {
        const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        window.location.href = `${loginUrl}?next=${encodeURIComponent(next)}`;
    }

    function toggleFavorite(article, button) {
        if (!isAuthenticated) {
            requireLogin();
            return;
        }
        const articleKey = getArticleKey(article);
        if (!articleKey) {
            showMessage("该论文缺少可收藏的标识。", "danger");
            return;
        }

        const favorite = !state.favoriteKeys.has(articleKey);
        if (button) button.disabled = true;
        fetch("/api/library/favorite", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ favorite, article: getArticleSnapshot(article) })
        })
            .then(async (response) => {
                const data = await response.json();
                if (response.status === 401) {
                    requireLogin();
                    return null;
                }
                if (!response.ok) throw new Error(data.message || "收藏操作失败");
                return data;
            })
            .then((data) => {
                if (!data) return;
                if (data.favorite) state.favoriteKeys.add(data.articleKey);
                else state.favoriteKeys.delete(data.articleKey);
                syncFavoriteButtons(data.articleKey);
                showMessage(data.favorite ? "已加入收藏。" : "已取消收藏。", "info");
            })
            .catch((error) => showMessage(error.message || "收藏操作失败。", "danger"))
            .finally(() => {
                if (button) button.disabled = false;
            });
    }

    function syncFavoriteButtons(articleKey = "") {
        document.querySelectorAll("[data-favorite-key]").forEach((button) => {
            const key = button.dataset.favoriteKey;
            if (articleKey && key !== articleKey) return;
            const favorite = state.favoriteKeys.has(key);
            button.classList.toggle("favorite-active", favorite);
            button.classList.toggle("active", favorite);
            button.setAttribute("aria-pressed", String(favorite));
            const label = button.querySelector("span");
            if (label) label.textContent = favorite ? "已收藏" : "收藏";
            else button.textContent = favorite ? "已收藏" : "收藏论文";
        });
    }

    function recordArticleRead(article) {
        if (!isAuthenticated || !getArticleKey(article)) return;
        fetch("/api/library/read", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ article: getArticleSnapshot(article) })
        }).catch((error) => console.error("保存阅读记录失败:", error));
    }

    function restoreStateFromUrl() {
        const params = new URLSearchParams(window.location.search);
        state.keyword = params.get("q") || "";
        state.subject = params.get("subject") || "全部";
        state.journal = params.get("journal") || "全部";
        state.dateRange = params.get("range") || "all";
        state.sort = params.get("sort") || "newest";
        state.page = Math.max(1, Number.parseInt(params.get("page") || "1", 10) || 1);
    }

    function syncControls() {
        if (elements.searchInput) elements.searchInput.value = state.keyword;
        if (elements.clearSearchButton) elements.clearSearchButton.hidden = !state.keyword;
        if (elements.journalFilter) elements.journalFilter.value = state.journal;
        if (elements.dateFilter) elements.dateFilter.value = state.dateRange;
        if (elements.sortFilter) elements.sortFilter.value = state.sort;

        elements.subjectFilter?.querySelectorAll(".tag-pill").forEach((button) => {
            button.classList.toggle("active", button.dataset.subject === state.subject);
        });
    }

    function loadArticlesData() {
        showLoading(true);
        fetch("/articles")
            .then((response) => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then((data) => {
                state.articles = Array.isArray(data) ? data.map(normalizeArticle) : [];
                generateSubjectFilters();
                generateJournalFilters();
                syncControls();
                applyState(false);
            })
            .catch((error) => {
                console.error("获取数据失败:", error);
                state.articles = [];
                applyState(false);
                showMessage("暂时无法获取论文数据，请稍后重试。", "danger");
            })
            .finally(() => showLoading(false));
    }

    function normalizeArticle(article, index) {
        const publishDate = article.date || article.publishDate || "";
        return {
            ...article,
            _id: article.doi || article.url || `article-${index}`,
            publishDate,
            normalizedDate: standardizeDate(publishDate),
            normalizedTags: normalizeTags(article.tags)
        };
    }

    function standardizeDate(dateString) {
        if (!dateString) return "";
        const parsedDate = new Date(dateString);
        if (!Number.isNaN(parsedDate.getTime())) {
            return parsedDate.toISOString().split("T")[0];
        }

        const yearFirst = dateString.match(/(\d{4})[/-](\d{1,2})[/-](\d{1,2})/);
        if (yearFirst) {
            return `${yearFirst[1]}-${yearFirst[2].padStart(2, "0")}-${yearFirst[3].padStart(2, "0")}`;
        }

        const dayFirst = dateString.match(/(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
        if (dayFirst) {
            return `${dayFirst[3]}-${dayFirst[2].padStart(2, "0")}-${dayFirst[1].padStart(2, "0")}`;
        }
        return "";
    }

    function getDateParts(dateString) {
        const normalizedDate = standardizeDate(dateString);
        if (!normalizedDate) return { primary: "未知", secondary: "日期", full: "未知日期" };
        const [year, month, day] = normalizedDate.split("-");
        return {
            primary: `${month}.${day}`,
            secondary: year,
            full: `${year}年${month}月${day}日`
        };
    }

    function normalizeTags(tags) {
        if (Array.isArray(tags)) {
            return tags.map(String).map((tag) => tag.trim()).filter(Boolean);
        }
        if (typeof tags === "string") {
            return tags.split(",").map((tag) => tag.trim()).filter(Boolean);
        }
        return [];
    }

    function generateSubjectFilters() {
        if (!elements.subjectFilter) return;
        const subjects = [...new Set(
            state.articles.map((article) => article.Subject?.trim()).filter(Boolean)
        )].sort((first, second) => first.localeCompare(second, "zh-CN"));

        if (state.subject !== "全部" && !subjects.includes(state.subject)) state.subject = "全部";
        elements.subjectFilter.replaceChildren();

        ["全部", ...subjects].forEach((subject) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `tag-pill${subject === state.subject ? " active" : ""}`;
            button.dataset.subject = subject;
            button.textContent = subject;
            button.addEventListener("click", () => {
                state.subject = subject;
                state.page = 1;
                elements.subjectFilter.querySelectorAll(".tag-pill").forEach((pill) => {
                    pill.classList.toggle("active", pill.dataset.subject === subject);
                });
                applyState();
            });
            elements.subjectFilter.appendChild(button);
        });
    }

    function generateJournalFilters() {
        if (!elements.journalFilter) return;
        const journals = [...new Set(
            state.articles.map((article) => article.journal?.trim()).filter(Boolean)
        )].sort((first, second) => first.localeCompare(second, "en"));

        if (state.journal !== "全部" && !journals.includes(state.journal)) state.journal = "全部";
        elements.journalFilter.replaceChildren(new Option("全部期刊", "全部"));
        journals.forEach((journal) => elements.journalFilter.add(new Option(journal, journal)));
    }

    function applySearch(showStatus) {
        const keyword = elements.searchInput?.value.trim() || "";
        if (keyword === state.keyword) return;
        state.keyword = keyword;
        state.page = 1;
        applyState();
        if (showStatus && keyword) {
            showMessage(`正在当前论文库中搜索“${keyword}”`, "info");
        }
    }

    function applyState(updateUrl = true) {
        const filteredArticles = getFilteredArticles();
        const totalPages = Math.max(1, Math.ceil(filteredArticles.length / articlesPerPage));
        state.page = Math.min(state.page, totalPages);
        renderArticles(filteredArticles);
        generatePagination(filteredArticles.length);
        renderActiveFilters();
        updateResultSummary(filteredArticles.length);
        syncControls();
        if (updateUrl) updateUrlState();
    }

    function getFilteredArticles() {
        const keyword = state.keyword.toLocaleLowerCase("zh-CN");
        const cutoffDate = getCutoffDate(state.dateRange);

        const filtered = state.articles.filter((article) => {
            if (state.subject !== "全部" && article.Subject?.trim() !== state.subject) return false;
            if (state.journal !== "全部" && article.journal?.trim() !== state.journal) return false;
            if (cutoffDate && (!article.normalizedDate || new Date(article.normalizedDate) < cutoffDate)) return false;

            if (keyword) {
                const searchableText = [
                    article.title,
                    article.titleCn,
                    article.abstract,
                    article.interpretationCn,
                    article.authors,
                    article.Subject,
                    article.journal,
                    article.doi,
                    ...article.normalizedTags
                ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
                if (!searchableText.includes(keyword)) return false;
            }
            return true;
        });

        return filtered.sort((first, second) => {
            if (state.sort === "oldest") return compareDates(first, second);
            if (state.sort === "title") {
                const firstTitle = first.titleCn || first.title || "";
                const secondTitle = second.titleCn || second.title || "";
                return firstTitle.localeCompare(secondTitle, "zh-CN");
            }
            return compareDates(second, first);
        });
    }

    function compareDates(first, second) {
        if (!first.normalizedDate) return 1;
        if (!second.normalizedDate) return -1;
        return new Date(first.normalizedDate) - new Date(second.normalizedDate);
    }

    function getCutoffDate(range) {
        if (range === "all") return null;
        const days = Number.parseInt(range, 10);
        if (!days) return null;
        const cutoff = new Date();
        cutoff.setHours(0, 0, 0, 0);
        cutoff.setDate(cutoff.getDate() - days);
        return cutoff;
    }

    function renderArticles(filteredArticles) {
        if (!elements.articlesList) return;
        const start = (state.page - 1) * articlesPerPage;
        const pageArticles = filteredArticles.slice(start, start + articlesPerPage);
        elements.articlesList.replaceChildren();

        if (!pageArticles.length) {
            const emptyState = document.createElement("div");
            emptyState.className = "no-results";
            const title = document.createElement("strong");
            title.textContent = "没有找到匹配的论文";
            const description = document.createElement("p");
            description.textContent = "尝试减少筛选条件、调整发布时间或更换搜索词。";
            const resetButton = document.createElement("button");
            resetButton.type = "button";
            resetButton.className = "button button-secondary empty-reset-button";
            resetButton.textContent = "清除全部条件";
            resetButton.addEventListener("click", resetFilters);
            emptyState.append(title, description, resetButton);
            elements.articlesList.appendChild(emptyState);
            return;
        }

        if (state.sort === "title") {
            const titleGroup = document.createElement("section");
            titleGroup.className = "date-group";
            const titleSeparator = document.createElement("div");
            titleSeparator.className = "date-separator";
            const label = document.createElement("time");
            const primary = document.createElement("strong");
            primary.textContent = "A-Z";
            const secondary = document.createElement("span");
            secondary.textContent = "标题";
            label.append(primary, secondary);
            titleSeparator.appendChild(label);
            const group = document.createElement("div");
            group.className = "date-articles-group";
            pageArticles.forEach((article) => group.appendChild(createArticleCard(article)));
            titleGroup.append(titleSeparator, group);
            elements.articlesList.appendChild(titleGroup);
            return;
        }

        const articlesByDate = pageArticles.reduce((groups, article) => {
            const dateKey = article.normalizedDate || "未知日期";
            groups[dateKey] = groups[dateKey] || [];
            groups[dateKey].push(article);
            return groups;
        }, {});

        const dateKeys = Object.keys(articlesByDate);
        if (state.sort === "oldest") {
            dateKeys.sort((first, second) => new Date(first) - new Date(second));
        } else {
            dateKeys.sort((first, second) => new Date(second) - new Date(first));
        }

        dateKeys.forEach((dateKey) => {
            const dateGroup = document.createElement("section");
            dateGroup.className = "date-group";
            const dateSeparator = document.createElement("div");
            dateSeparator.className = "date-separator";
            const dateParts = getDateParts(dateKey);
            const time = document.createElement("time");
            time.dateTime = dateKey === "未知日期" ? "" : dateKey;
            const primary = document.createElement("strong");
            primary.textContent = dateParts.primary;
            const secondary = document.createElement("span");
            secondary.textContent = dateParts.secondary;
            time.append(primary, secondary);
            dateSeparator.appendChild(time);

            const group = document.createElement("div");
            group.className = "date-articles-group";
            articlesByDate[dateKey].forEach((article) => group.appendChild(createArticleCard(article)));
            dateGroup.append(dateSeparator, group);
            elements.articlesList.appendChild(dateGroup);
        });
    }

    function createArticleCard(article) {
        const card = document.createElement("article");
        card.className = "paper-card";

        const top = document.createElement("div");
        top.className = "paper-card-top";
        const source = document.createElement("div");
        source.className = "paper-source";
        if (article.journal) source.appendChild(createBadge(article.journal, "journal-badge"));
        if (article.Subject) source.appendChild(createBadge(article.Subject, "subject-badge"));
        const date = document.createElement("time");
        date.className = "paper-date";
        date.dateTime = article.normalizedDate;
        date.textContent = getDateParts(article.publishDate).full;
        top.append(source, date);

        const title = document.createElement("h3");
        title.className = "paper-title";
        const titleButton = document.createElement("button");
        titleButton.type = "button";
        titleButton.textContent = article.titleCn || article.title || "未命名论文";
        titleButton.addEventListener("click", () => showArticleDetails(article, titleButton));
        title.appendChild(titleButton);

        const originalTitle = document.createElement("p");
        originalTitle.className = "paper-original-title";
        originalTitle.textContent = article.title || "";

        const abstractWrap = document.createElement("div");
        abstractWrap.className = "paper-abstract-wrap";
        const abstractMark = document.createElement("span");
        abstractMark.className = "abstract-mark";
        abstractMark.textContent = "“";
        const abstract = document.createElement("p");
        abstract.className = "paper-abstract";
        abstract.textContent = article.interpretationCn || article.abstract || "暂无中文解读或摘要。";
        const expandButton = document.createElement("button");
        expandButton.type = "button";
        expandButton.className = "abstract-toggle";
        expandButton.textContent = "展开解读";
        expandButton.addEventListener("click", () => {
            const expanded = abstractWrap.classList.toggle("expanded");
            expandButton.textContent = expanded ? "收起解读" : "展开解读";
            expandButton.setAttribute("aria-expanded", String(expanded));
        });
        abstractWrap.append(abstractMark, abstract, expandButton);

        const footer = document.createElement("div");
        footer.className = "paper-footer";
        const metaFooter = document.createElement("div");
        metaFooter.className = "paper-meta-footer";
        const tags = document.createElement("div");
        tags.className = "paper-tags";
        article.normalizedTags.slice(0, 5).forEach((tag) => {
            const tagElement = document.createElement("button");
            tagElement.type = "button";
            tagElement.className = "paper-tag";
            tagElement.textContent = tag;
            tagElement.addEventListener("click", () => {
                elements.searchInput.value = tag;
                state.keyword = tag;
                state.page = 1;
                applyState();
            });
            tags.appendChild(tagElement);
        });
        metaFooter.appendChild(tags);

        if (article.doi) {
            const doi = document.createElement("span");
            doi.className = "paper-doi";
            doi.textContent = `DOI ${article.doi}`;
            doi.title = article.doi;
            metaFooter.appendChild(doi);
        }

        const actions = document.createElement("div");
        actions.className = "paper-actions";
        const favoriteButton = createFavoriteButton(article);
        const detailButton = createActionButton("查看详情");
        detailButton.addEventListener("click", () => showArticleDetails(article, detailButton));
        actions.append(favoriteButton, detailButton);
        if (article.url) actions.appendChild(createActionLink(article.url, "查看原文"));

        footer.append(metaFooter, actions);
        card.append(top, title, originalTitle, abstractWrap, footer);
        return card;
    }

    function createFavoriteButton(article) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "paper-action";
        button.dataset.favoriteKey = getArticleKey(article);
        button.innerHTML = `
            <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M10 16.5 4.4 11A3.8 3.8 0 0 1 9.8 5.6L10 5.8l.2-.2a3.8 3.8 0 0 1 5.4 5.4Z"></path>
            </svg>
            <span>收藏</span>
        `;
        button.addEventListener("click", () => toggleFavorite(article, button));
        const favorite = state.favoriteKeys.has(button.dataset.favoriteKey);
        button.classList.toggle("favorite-active", favorite);
        button.setAttribute("aria-pressed", String(favorite));
        button.querySelector("span").textContent = favorite ? "已收藏" : "收藏";
        return button;
    }

    function createBadge(text, className) {
        const badge = document.createElement("span");
        badge.className = `meta-badge ${className}`;
        badge.textContent = text;
        return badge;
    }

    function createActionButton(label) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "paper-action";
        button.innerHTML = `
            <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M3 10s2.5-4 7-4 7 4 7 4-2.5 4-7 4-7-4-7-4Z"></path>
                <circle cx="10" cy="10" r="1.8"></circle>
            </svg>
            <span>${label}</span>
        `;
        return button;
    }

    function createActionLink(url, label) {
        const link = document.createElement("a");
        link.className = "paper-action paper-action-primary";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.innerHTML = `
            <span>${label}</span>
            <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M7.5 5.5h7v7M14 6l-8.5 8.5"></path>
            </svg>
        `;
        return link;
    }

    function renderActiveFilters() {
        if (!elements.activeFilters) return;
        elements.activeFilters.replaceChildren();
        const filters = [];
        if (state.keyword) filters.push({ label: `搜索：${state.keyword}`, reset: () => { state.keyword = ""; } });
        if (state.subject !== "全部") filters.push({ label: state.subject, reset: () => { state.subject = "全部"; } });
        if (state.journal !== "全部") filters.push({ label: state.journal, reset: () => { state.journal = "全部"; } });
        if (state.dateRange !== "all") {
            const label = elements.dateFilter?.selectedOptions[0]?.textContent || "发布时间";
            filters.push({ label, reset: () => { state.dateRange = "all"; } });
        }

        filters.forEach((filter) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "active-filter-chip";
            chip.textContent = `${filter.label} ×`;
            chip.addEventListener("click", () => {
                filter.reset();
                state.page = 1;
                applyState();
            });
            elements.activeFilters.appendChild(chip);
        });
        elements.activeFilters.classList.toggle("visible", filters.length > 0);
    }

    function updateResultSummary(count) {
        if (!elements.resultSummary) return;
        const start = count ? (state.page - 1) * articlesPerPage + 1 : 0;
        const end = Math.min(state.page * articlesPerPage, count);
        elements.resultSummary.textContent = count
            ? `共 ${count} 篇 · 当前显示 ${start}-${end}`
            : "没有匹配结果";
    }

    function generatePagination(totalArticles) {
        if (!elements.pagination) return;
        const totalPages = Math.ceil(totalArticles / articlesPerPage);
        elements.pagination.replaceChildren();
        if (totalPages <= 1) return;

        const addPageButton = (label, page, options = {}) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `page-item${options.active ? " active" : ""}${options.disabled ? " disabled" : ""}`;
            button.textContent = label;
            button.disabled = Boolean(options.disabled);
            if (!options.disabled) {
                button.addEventListener("click", () => {
                    state.page = page;
                    applyState();
                    document.getElementById("papers")?.scrollIntoView({ behavior: "smooth" });
                });
            }
            elements.pagination.appendChild(button);
        };

        addPageButton("上一页", state.page - 1, { disabled: state.page === 1 });
        const startPage = Math.max(1, Math.min(state.page - 2, totalPages - 4));
        const endPage = Math.min(totalPages, startPage + 4);
        for (let page = startPage; page <= endPage; page += 1) {
            addPageButton(String(page), page, { active: page === state.page });
        }
        addPageButton("下一页", state.page + 1, { disabled: state.page === totalPages });
    }

    function updateUrlState() {
        const params = new URLSearchParams();
        if (state.keyword) params.set("q", state.keyword);
        if (state.subject !== "全部") params.set("subject", state.subject);
        if (state.journal !== "全部") params.set("journal", state.journal);
        if (state.dateRange !== "all") params.set("range", state.dateRange);
        if (state.sort !== "newest") params.set("sort", state.sort);
        if (state.page > 1) params.set("page", String(state.page));
        const query = params.toString();
        const url = `${window.location.pathname}${query ? `?${query}` : ""}#papers`;
        window.history.replaceState({}, "", url);
    }

    function resetFilters() {
        state.keyword = "";
        state.subject = "全部";
        state.journal = "全部";
        state.dateRange = "all";
        state.sort = "newest";
        state.page = 1;
        applyState();
    }

    function handleAssistantSubmit(event) {
        event.preventDefault();
        const message = elements.researchQuestion?.value.trim() || "";
        if (message.length < 4) {
            renderAssistantError("请稍微详细描述你的研究需求。");
            return;
        }

        setAssistantLoading(true);
        fetch("/api/research-assistant", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        })
            .then(async (response) => {
                const data = await response.json();
                if (!response.ok) throw new Error(data.message || "请求失败");
                return data;
            })
            .then(renderAssistantResponse)
            .catch((error) => {
                console.error("科研数据推荐失败:", error);
                renderAssistantError(error.message || "暂时无法完成推荐，请稍后重试。");
            })
            .finally(() => setAssistantLoading(false));
    }

    function setAssistantLoading(isLoading) {
        if (!elements.askAssistantButton) return;
        elements.askAssistantButton.disabled = isLoading;
        const label = elements.askAssistantButton.querySelector("span");
        if (label) label.textContent = isLoading ? "正在分析..." : "查找数据";
    }

    function renderAssistantResponse(data) {
        if (!elements.assistantResponse) return;
        elements.assistantResponse.replaceChildren();
        elements.assistantResponse.classList.add("visible");

        const answer = document.createElement("div");
        answer.className = "assistant-answer";
        const avatar = document.createElement("span");
        avatar.className = "message-avatar";
        avatar.textContent = "AI";
        const answerText = document.createElement("div");
        answerText.className = "assistant-answer-text";
        const paragraph = document.createElement("p");
        paragraph.textContent = data.answer || "根据你的研究需求，推荐以下数据论文。";
        const mode = document.createElement("span");
        mode.className = "assistant-mode";
        mode.textContent = data.mode === "ai" ? "由大模型结合论文库生成" : "当前使用本地论文库匹配";
        answerText.append(paragraph, mode);
        answer.append(avatar, answerText);
        elements.assistantResponse.appendChild(answer);

        const recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
        if (!recommendations.length) return;

        const grid = document.createElement("div");
        grid.className = "assistant-recommendations";
        recommendations.forEach((recommendation, index) => {
            const article = normalizeArticle(recommendation, index);
            const card = document.createElement("article");
            card.className = "assistant-result-card";
            const meta = document.createElement("div");
            meta.className = "assistant-result-meta";
            if (article.journal) meta.appendChild(createBadge(article.journal, "journal-badge"));
            if (article.Subject) meta.appendChild(createBadge(article.Subject, "subject-badge"));
            const title = document.createElement("h3");
            title.textContent = article.titleCn || article.title || "未命名数据论文";
            const reason = document.createElement("p");
            reason.className = "assistant-result-reason";
            reason.textContent = article.reason || "与当前研究需求具有较高相关性。";
            const actions = document.createElement("div");
            actions.className = "assistant-result-actions";
            const detailButton = document.createElement("button");
            detailButton.type = "button";
            detailButton.textContent = "查看详情";
            detailButton.addEventListener("click", () => showArticleDetails(article, detailButton));
            actions.appendChild(detailButton);
            if (article.url) {
                const link = document.createElement("a");
                link.href = article.url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "打开原文";
                actions.appendChild(link);
            }
            card.append(meta, title, reason, actions);
            grid.appendChild(card);
        });
        elements.assistantResponse.appendChild(grid);
    }

    function renderAssistantError(message) {
        if (!elements.assistantResponse) return;
        elements.assistantResponse.replaceChildren();
        elements.assistantResponse.classList.add("visible");
        const error = document.createElement("div");
        error.className = "assistant-error";
        error.textContent = message;
        elements.assistantResponse.appendChild(error);
    }

    function showArticleDetails(article, trigger) {
        if (!elements.modal) return;
        activeModalArticle = article;
        lastFocusedElement = trigger || document.activeElement;
        document.getElementById("modalTitle").textContent = article.titleCn || article.title || "论文详情";
        document.getElementById("modalAuthors").textContent = article.authors || "作者信息暂缺";
        document.getElementById("modalDate").textContent = `发布日期：${getDateParts(article.publishDate).full}`;
        document.getElementById("modalAbstract").textContent =
            article.interpretationCn || article.abstract || "暂无中文解读或摘要。";

        const doiElement = document.getElementById("modalDoi");
        if (article.doi) {
            doiElement.style.display = "";
            doiElement.querySelector("span").textContent = article.doi;
        } else {
            doiElement.style.display = "none";
        }

        const datasetsList = document.querySelector("#modalDatasets .datasets-list");
        datasetsList.replaceChildren();
        const datasetLinks = Array.isArray(article.dataset_links) ? article.dataset_links : [];
        if (datasetLinks.length) {
            datasetLinks.forEach((url) => {
                const item = document.createElement("li");
                const link = document.createElement("a");
                link.href = url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = url;
                item.appendChild(link);
                datasetsList.appendChild(item);
            });
        } else {
            const item = document.createElement("li");
            item.textContent = "暂无相关数据集链接";
            datasetsList.appendChild(item);
        }

        const modalLink = document.getElementById("modalLink");
        modalLink.href = article.url || "#";
        modalLink.style.display = article.url ? "inline-flex" : "none";
        if (elements.modalFavoriteButton) {
            elements.modalFavoriteButton.dataset.favoriteKey = getArticleKey(article);
            syncFavoriteButtons(getArticleKey(article));
        }
        elements.modal.classList.add("visible");
        document.body.classList.add("modal-open");
        elements.closeModalButton?.focus();
        recordArticleRead(article);
    }

    function closeModal() {
        elements.modal?.classList.remove("visible");
        document.body.classList.remove("modal-open");
        activeModalArticle = null;
        lastFocusedElement?.focus();
    }

    function showLoading(isLoading) {
        if (elements.loadingOverlay) {
            elements.loadingOverlay.style.display = isLoading ? "flex" : "none";
        }
    }

    function showMessage(message, type = "info") {
        if (!elements.statusMessage) return;
        elements.statusMessage.textContent = message;
        elements.statusMessage.className = `alert alert-${type}`;
        elements.statusMessage.style.display = "block";
        window.setTimeout(() => {
            elements.statusMessage.style.display = "none";
        }, 3000);
    }
});
