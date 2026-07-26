---
version: 0.1
name: ME.xyz-design-system
description: 克制、有分寸感的"人生模拟器"视觉系统。底色沿用编辑部式的暖白画布，黑白灰承载绝大多数界面，五个低饱和强调色只出现在"未来的自己"角色卡片与图谱节点上——用来标记不同人生路径的情绪基调，而不是用来做装饰。字体上英文统一用 Tahoma，中文统一用非衬线体苹方（PingFang SC），全站无衬线，保证标题与长对话场景下的可读性一致。整体审美参照 ElevenLabs 的克制感，但把它唯一的"彩色时刻"从纯装饰的渐变光斑，改造成真正承载信息的角色/节点强调色。
---

## 总览

ME.xyz 不是一个讨好型陪伴产品，也不是说教型工具，视觉上要同时避免"甜腻治愈系"和"高冷科技感"。参照对象 ElevenLabs 提供的底子——暖白画布、hairline 描边卡片、pill 按钮、96px 呼吸感——正好符合"克制但不冷漠"的调性。与源文档最大的差异：

1. **字体全面替换为系统字体**：Waldenburg 是拉丁专属付费字体，无法承载中文标题，改用英文 Tahoma + 中文苹方（PingFang SC）的无衬线组合，全站不使用衬线体。
2. **强调色从纯装饰变为信息载体**：ElevenLabs 的 5 个渐变色只用来做背景光斑，不承载语义；ME.xyz 的 5 个强调色分别对应角色卡片/图谱节点的"情绪基调"分类，是界面的一部分。

## 色彩

### 基础色板（黑白灰，承载 90% 界面）

| Token | 色值 | 用途 |
|---|---|---|
| `color.canvas` | #FDFCFC | 页面底色 |
| `color.canvas-soft` | #fafafa | 次级底色，用于分区 |
| `color.surface-card` | #ffffff | 卡片、弹层 |
| `color.surface-strong` | #f0efed | 徽标底、输入框底 |
| `color.ink` | #0c0a09 | 标题、强调文字、主按钮底色 |
| `color.ink-soft` | #292524 | 次级标题 |
| `color.body` | #4e4e4e | 正文 |
| `color.muted` | #777169 | 辅助说明文字 |
| `color.muted-soft` | #a8a29e | 禁用态、占位文字 |
| `color.hairline` | #e7e5e4 | 默认描边/分割线 |
| `color.hairline-strong` | #d6d3d1 | 强调描边（输入框、卡片选中态） |
| `color.on-primary` | #ffffff | 黑底按钮上的文字 |

### 强调色（角色卡片 / 图谱节点专用，克制使用）

不用于按钮、不用于大面积背景，只用于卡片顶部色条、标签底色、图谱节点填充——用来区分"未来的自己"的五种情绪基调。

| Token | 色值 | 情绪基调示例 |
|---|---|---|
| `color.accent-moss`（苔绿） | #6b8f71 | 松弛 / 与自己和解 |
| `color.accent-slate`（雾蓝） | #5c7a99 | clarity / 想清楚了 |
| `color.accent-ochre`（陶土黄） | #b08a3e | 踏实 / 稳定积累 |
| `color.accent-plum`（暗紫） | #8b7098 | 复杂 / 有代价的自由 |
| `color.accent-rose`（灰玫瑰） | #b98289 | 柔软 / 仍在和解中 |

### 核心色板（品牌马卡龙色，全站可用，克制使用）

这是 ME.xyz 的核心品牌色板，最早在 PainPoints 情景故事卡片上使用，现在是全站通用的强调色资源池（Team 成员卡片身份标签等场景同样取自这里）——语境不同，色板同源：角色卡片标记"未来的自己"的性格基调，情景故事卡片标记"当下这段叙述"的情绪基调，Team 卡片标记"这个人"的身份识别。同样遵循"不用于按钮/大面积背景、单屏最多同时出现 3 种"的克制原则；纯黑纯白仅作为品牌基准色参照，日常界面仍分别使用 `color.ink`（#0c0a09，更暖）与 `color.surface-card`（#ffffff）。

| Token | 色值 | 中文名 |
|---|---|---|
| `color.core-black` | #000000 | 纯黑（品牌基准色，UI 中优先用 `color.ink`） |
| `color.story-sky` | #CAE8FF | 天空蓝 / 婴儿蓝 |
| `color.story-mint` | #D4F9E1 | 薄荷绿 |
| `color.story-lavender` | #F0D4FF | 薰衣草紫 |
| `color.story-coral` | #FFCACB | 珊瑚粉 |
| `color.story-sakura` | #FFE3F5 | 樱花粉 |
| `color.story-vanilla` | #FFECBD | 香草黄 |
| `color.story-white` | #FFFFFF | 纯白（等同 `color.surface-card`） |

### 语义色

| Token | 色值 | 用途 |
|---|---|---|
| `color.success` | #16a34a | 保存成功等确认态 |
| `color.error` | #dc2626 | 表单校验错误 |

## 字体

| 角色 | 字体栈 | 场景 |
|---|---|---|
| 展示体 `font.display` | `'Tahoma', 'PingFang SC', 'Microsoft YaHei', sans-serif`，字重 300/400 | 大标题、"我已经看到了未来不同版本的你"这类关键话术、角色卡片标题 |
| 正文体 `font.body` | `'Tahoma', 'PingFang SC', 'Microsoft YaHei', sans-serif` | 对话气泡、说明文字、按钮、导航 |
| 数字/英文 | `'Tahoma'` | 时间戳、百分比等 |

原则：英文统一用 Tahoma，中文统一用非衬线体苹方（PingFang SC），全站不再使用衬线字体；均为系统自带字体，无需额外加载 Web Font。

### 字号阶梯

| Token | 字号 | 字重 | 场景 |
|---|---|---|---|
| `type.display-lg` | 44px / 300 | 首页大标题、Onboarding 问题标题 |
| `type.display-md` | 31px / 300 | 板块标题、"我已经看到了未来..."引导语 |
| `type.title` | 20px / 500 | 卡片标题、角色身份标签 |
| `type.body` | 16.5px / 400 | 对话正文、说明文字 |
| `type.body-sm` | 14px / 400 | 时间戳、辅助信息 |
| `type.caption` | 13px / 500，字间距 0.6px，大写/加粗中文用等宽处理 | 标签、徽标文字 |

> 2026-07-25 起全站字号在此基础上统一上调约 10%（原字号见 git 历史/旧版备份），保持阶梯比例不变，仅整体放大以增强可读性与视觉分量。

### 斜体使用原则

全站斜体只用于两种场景，二者不混用：

- **故事/章节标题**（如 Onboarding 情景题标题"岸边的风"、PainPoints 故事卡片标题"不敢选的你"）：`font.display` + 斜体，字重 400，强化"叙事感"。
- **引述/心声类文案**（如首页"本周的一句话"、PainPoints 的"一句话痛点"与"真实心声"）：`font.display`，字重 300，**不用斜体**，用中文引号包裹——这类文案是"被引用的话"，保持直体以区别于上面的故事标题，避免斜体滥用。
- **例外——Team 成员卡片的个人 slogan**：紧贴姓名下方的一句话签名（如"The universe is a continuous web..."）视为"故事标题"一类的身份化表达而非"被引用的话"，走斜体，`muted` 色，字号小于正文，与角色/情景故事标题共用同一条斜体规则。

## 圆角与间距

沿用源文档的比例关系（pill 按钮 + xl 卡片 + 克制的描边），数值不变：

`radius.xs 4px` · `radius.sm 6px` · `radius.md 8px` · `radius.lg 12px` · `radius.xl 16px` · `radius.xxl 24px` · `radius.pill 9999px`

`space.xxs 4px` · `space.xs 8px` · `space.sm 12px` · `space.base 16px` · `space.md 20px` · `space.lg 24px` · `space.xl 32px` · `space.xxl 48px`

## 关键组件

- **top-nav**：`canvas` 底色，64px 高，居中 Tab（首页/对话/未来的我/记忆图谱/思维溯源/我的），当前 Tab 用 `ink` 实心药丸背景标记。
- **role-card**：白底卡片，顶部 4px 强调色色条（对应情绪基调），标题用 `display-md`，包含"关键选择路径/日常切片/代价与获得/情绪基调"四行摘要，`radius.xl`，hover 时 `0 4px 16px rgba(0,0,0,.06)` 阴影上浮。
- **chat-sidebar**：240px 宽，`canvas-soft` 底，置顶"主聊天"入口，下方角色历史列表每项左侧 4px 强调色竖条 + 角色标题。
- **chat-bubble**：用户气泡 `ink` 底白字靠右；Agent 气泡 `surface-card` 白底 + `hairline` 描边靠左。
- **graph-node**：圆形节点，中心"你"用 `ink` 实心，子节点按情绪基调用对应强调色的浅底 + 强调色描边，点击后底部弹出摘要卡片。
- **badge-pill**：`surface-strong` 底，`caption` 字号，`radius.pill`，用于图谱节点类型标签、卡片情绪基调标签。
- **story-tab-card**：分段式胶囊 Tab 切换（非轮播），一次只显示一个故事卡片；卡片顶部为强调色标签（取自故事卡片专用色板）+ eyebrow（STORY A/B/C），标题走斜体故事标题规则，正文中嵌入一条同色浅底的引述卡片作为视觉停顿点。
- **pull-quote**：引述类文案的容器，`font.display` 字重 300、不斜体、中文引号包裹，用于把长段落中最值得记住的一句话单独摘出。
- **numbered-insight-list**：编号列表（如 Why It Matters），每项由加粗深色的一句话结论 + 字号略小、`muted` 色的解释性文字组成——用字重/颜色的落差制造扫读层级，而不是隐藏或折叠内容。
- **team-card**：白底卡片，`radius.xl`，顶部"姓名缩写方块 + 中英文姓名"，下接核心色板色底的身份标签（`badge-pill`）、`pull-quote` 风格的一句话签名、正文简介、`skill` 标签行、底部按钮走 `btn-outline`（小尺寸变体，hover 反色为 `ink`）——占位成员（尚未提供介绍）用 `hairline-strong` 虚线边框 + `muted-soft` 文案代替真实内容，不臆造人设。

## 布局宽度

内容型页面（首页、PainPoints、Team、Vision、人格网格、我的）的滚动容器 `max-width` 统一为 **1280px**（原 960px，2026-07-25 起加宽，占常见 1440~1920 桌面视口约 2/3，增强卡片区与正文的视觉分量）；页内受限宽度的文案元素（首页大标题/副标题、Vision Hero 标题等）按同比例（约 1.33×）一并加宽。表单类窄容器（登录页 `login-shell` 440px、Onboarding `onb-host` 460px）维持不变——聚焦单一操作的页面不套用加宽规则。

## 按钮尺寸

| Token | Padding | 字号 | 场景 |
|---|---|---|---|
| `btn.size-md`（默认） | 13px 26px | 15.5px | Hero CTA（如首页 Log in / Contact Builder） |
| `btn.size-sm` | 8px 16px | 14px | 卡片内联操作（如 Team 成员卡片的外部链接） |

两种尺寸共用同一套 `btn-primary`（`ink` 实底）/ `btn-outline`（描边，hover 反色）视觉规则，只是内边距与字号按场景缩放，保证"卡片里的按钮"与"Hero 里的按钮"是同一套语言的两种字号，而不是两套设计。

## 图标

统一使用 **Phosphor Icons**（Regular 线框为主，情绪/首页强调场景可用 Duotone 权重点缀），2px 描边，圆角端点，24px 网格，风格与整体"圆角、简洁"的方向一致，中文界面下大小写混排也不违和。

## Do / Don't

**Do**
- 强调色只用于角色卡片色条、图谱节点、情绪标签——保持"信息性"而非"装饰性"。
- 展示体中文标题字重不超过 400。
- 对话气泡、按钮统一走 `radius.pill` 或 `radius.xl`，不出现直角卡片。

**Don't**
- 不要在按钮、大面积背景上使用强调色——`ink` 黑色药丸是唯一的主按钮色。
- 不要五个强调色同屏滥用，单个页面/单次卡片生成最多同时出现 3 种。
- 不要给中文正文使用衬体，长对话场景衬体降低可读性。
