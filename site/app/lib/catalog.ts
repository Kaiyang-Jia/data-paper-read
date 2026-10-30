import type { Assessment, DataProfile, Requirements } from './requirements';
export type Article = {
  id?: string;
  title: string;
  titleCn?: string;
  interpretationCn?: string;
  chineseProcessing?: {model: string; generatedAt: string; status: string; basis: string; revision: string};
  abstract?: string;
  publishDate?: string;
  doi?: string;
  url?: string;
  authors?: string;
  tags?: string[];
  Subject?: string;
  journal?: string;
  reason?: string;
  matchedTerms?: string[];
  evidence?: { field: string; text: string };
  dataProfile?: DataProfile | null;
  requirementsAssessment?: Assessment;
};
export type Catalog = {
  articles: Article[];
  summary: { generatedAt?: string; source?: string; totalCount?: number; subjects?: string[]; journals?: string[]; years?: string[]; subjectCounts?: Record<string, number>; latestPublishDate?: string };
  pagination?: {page: number; total: number; size: number};
  capabilities?: {
    assistant: boolean;
    generationConfigured?: boolean;
    semanticConfigured?: boolean;
  };
};
export type ResearchResult = {
  mode: string;
  answer: string;
  recommendations: Article[];
  requirements?: Requirements;
};
export const keyOf = (a: Article) =>
  (a.doi || a.url || a.title).trim().toLowerCase();
export function sourceUrl(a: Article) {
  if (a.doi && /^10\.\d{4,9}\//.test(a.doi))
    return `https://doi.org/${encodeURI(a.doi).replace(/[?#]/g, encodeURIComponent)}`;
  try {
    const url = new URL(a.url || "");
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}
// Exclude processing notices and placeholder values from presentation only.
export function contentText(value?: string): string {
  if (!value?.trim()) return '';
  const text = value.trim();
  if (/^(暂无数据|未提供|未识别|未分类|待核实|未知|N\/A|null|none|-)$/i.test(text)) return '';
  return text.split(/(?<=[。！？\n])/).filter(part => !/仅依据标题|当前缺少摘要|尚未人工复核|模型整理|信息尚未验证|仅供参考|需.*(?:查看原文核实|进一步核实)|待核实|待复核|需复核|需核验|尚未验证|尚未核验|尚未进行模型|仅元数据|AI整理|AI解读|智能提取|模型判断|依据[：:]标题/.test(part)).join('').trim();
}
export function presentArticle(a: Article): Article {
  return {...a, titleCn: contentText(a.titleCn), abstract: contentText(a.abstract),
    interpretationCn: a.chineseProcessing?.basis === 'title' ? '' : contentText(a.interpretationCn),
    journal: contentText(a.journal), publishDate: contentText(a.publishDate),
    Subject: contentText(a.Subject), authors: contentText(a.authors), doi: contentText(a.doi)};
}
export function normalizeCatalog(payload: Catalog): Catalog {
  if (!payload || !Array.isArray(payload.articles))
    throw new Error("论文数据格式异常");
  const seen = new Set<string>();
  const articles = payload.articles
    .filter((a) => {
      if (!a || typeof a.title !== "string" || !a.title.trim()) return false;
      const key = keyOf(a);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((a) => ({
      ...presentArticle(a),
      tags: Array.isArray(a.tags)
        ? a.tags.filter((t) => typeof t === "string")
        : [],
    }));
  return { ...payload, articles };
}
const concepts: Record<string, string[]> = {
  城市: ["urban", "city", "cities"],
  热岛: ["heat island", "temperature"],
  气候: ["climate"],
  遥感: ["remote sensing", "satellite"],
  土地: ["land use", "land cover"],
  碳排放: ["carbon", "emission"],
  人口: ["population"],
  水文: ["hydrolog", "streamflow", "river"],
  河流: ["river"],
  中国: ["china", "chinese"],
  生态: ["ecolog", "ecosystem"],
  生物多样性: ["biodiversity", "species"],
  农业: ["agricultur", "crop"],
  蛋白质: ["protein"],
  基因: ["gene", "genom"],
  海洋: ["ocean", "marine"],
  污染: ["pollution", "pollutant"],
  降水: ["precipitation", "rainfall"],
  土壤: ["soil"],
  机器学习: ["machine learning"],
};
export function queryTerms(query: string) {
  return [
    ...new Set([
      ...query
        .toLowerCase()
        .split(/[\s,，;；。]+/)
        .filter(Boolean),
      ...Object.entries(concepts)
        .filter(([word]) => query.includes(word))
        .flatMap(([, terms]) => terms),
    ]),
  ];
}
export function matchScore(a: Article, query: string) {
  const title = `${a.title} ${a.titleCn || ""}`.toLowerCase();
  const text =
    `${a.abstract || ""} ${a.interpretationCn || ""} ${a.Subject || ""} ${(a.tags || []).join(" ")}`.toLowerCase();
  return queryTerms(query).reduce(
    (sum, term) =>
      sum + (title.includes(term) ? 6 : text.includes(term) ? 1 : 0),
    0,
  );
}
export function localResearch(
  articles: Article[],
  query: string,
): ResearchResult {
  const terms = queryTerms(query);
  const ranked = articles
    .map((a) => ({ a, score: matchScore(a, query) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  return {
    mode: "offline",
    answer: ranked.length
      ? "相关文献"
      : "当前快照中没有找到匹配论文。请尝试更具体的数据对象，或改用英文关键词。",
    recommendations: ranked.map(({ a }) => ({
      ...a,
      reason: "",
      matchedTerms: terms.filter((t) =>
        `${a.title} ${a.abstract || ""}`.toLowerCase().includes(t),
      ),
      evidence: {
        field: a.abstract ? "abstract" : "title",
        text: a.abstract
          ? (
              a.abstract
                .split(/(?<=[.!?])\s+/)
                .find((s) => terms.some((t) => s.toLowerCase().includes(t))) ||
              a.abstract
            ).slice(0, 650)
          : a.title,
      },
    })),
  };
}
export function exportBrief(
  articles: Article[],
  query: string,
  notes: Record<string, string>,
  requirements?: Requirements,
  labels: Record<string, string> = {},
) {
  return [
    "# DataPaper · 科研数据候选清单",
    "",
    `导出时间：${new Date().toISOString()}`,
    ...(query ? [`研究需求：${query}`] : []),
    ...(requirements?.conditions.length ? ['需求条件：', ...requirements.conditions.map(c => `- ${labels[c.field] || c.field.replace(/^custom:/, '')}（${c.priority === 'required' ? '必须' : '偏好'}）：${Array.isArray(c.value) ? c.value.join('，') : c.value}`)] : []),
    "",
    "",
    ...articles.flatMap((a, i) => [
      `## ${i + 1}. ${a.titleCn || a.title}`,
      a.titleCn ? a.title : "",
      [a.journal, a.publishDate].filter(Boolean).join(" | "),
      a.doi ? `DOI：${a.doi}` : "",
      sourceUrl(a) ? `原文：${sourceUrl(a)}` : "",
      "",
      a.abstract ? `摘要：${a.abstract}` : "",
      a.interpretationCn ? `内容简介：${a.interpretationCn}` : "",
      "",
      notes[keyOf(a)] ? `个人笔记：${notes[keyOf(a)]}` : "",
      "",
      "",
    ]),
  ].join("\n");
}
