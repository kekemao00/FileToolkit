"""
提示词模板库

每个模板包含：
- id: 唯一标识
- name: 显示名称
- description: 简短描述
- category: 分类
- icon: 图标名称（Material Icons 枚举名，大写下划线形式）
- tags: 标签列表
- prompt_template: 提示词模板（{变量名} 为占位符）
- variables: 变量定义列表，每个包含 name, label, type, options, placeholder, required, default
- default_size: 默认图片尺寸
"""
from __future__ import annotations

# 分类列表（全部排在最前，用于 UI 过滤栏）
CATEGORIES = ["全部", "海报", "社交媒体", "Logo", "产品", "艺术", "其他"]

TEMPLATES: list[dict] = [
    {
        "id": "poster_minimal",
        "name": "简约海报",
        "description": "极简风格的活动/宣传海报",
        "category": "海报",
        "icon": "ARTICLE",
        "tags": ["热门", "海报"],
        "prompt_template": (
            "Design a minimalist poster for '{theme}'. "
            "Main title: '{title}', subtitle: '{subtitle}'. "
            "Style: {style}. Color scheme: {color_scheme}. "
            "Layout: clean, modern, with ample white space. "
            "Typography should be elegant and readable. "
            "No clutter, focus on visual hierarchy."
        ),
        "variables": [
            {"name": "theme", "label": "主题", "type": "text",
             "placeholder": "如：2026春季音乐节", "required": True},
            {"name": "title", "label": "主标题", "type": "text",
             "placeholder": "如：春之声", "required": True},
            {"name": "subtitle", "label": "副标题", "type": "text",
             "placeholder": "如：2026.05.20 城市音乐厅", "required": False, "default": ""},
            {"name": "style", "label": "风格", "type": "select",
             "options": ["极简主义", "瑞士平面设计", "日式侘寂", "北欧风格"],
             "default": "极简主义"},
            {"name": "color_scheme", "label": "配色方案", "type": "select",
             "options": ["黑白灰", "莫兰迪色系", "蓝白经典", "暖色调", "冷色调"],
             "default": "黑白灰"},
        ],
        "default_size": "1024x1536",
    },
    {
        "id": "poster_tech",
        "name": "科技海报",
        "description": "未来感十足的科技/发布会海报",
        "category": "海报",
        "icon": "ROCKET_LAUNCH",
        "tags": ["科技", "海报"],
        "prompt_template": (
            "Create a futuristic tech poster for '{event_name}'. "
            "Theme: {theme}. Style: {style} with {color_scheme} color palette. "
            "Include abstract tech elements like circuits, particles, or data streams. "
            "Typography: bold, modern sans-serif. "
            "Atmosphere: {atmosphere}. High contrast, dramatic lighting."
        ),
        "variables": [
            {"name": "event_name", "label": "活动/产品名称", "type": "text",
             "placeholder": "如：AI Summit 2026", "required": True},
            {"name": "theme", "label": "主题", "type": "text",
             "placeholder": "如：人工智能改变未来", "required": True},
            {"name": "style", "label": "视觉风格", "type": "select",
             "options": ["赛博朋克", "全息投影", "暗黑科技", "太空探索"],
             "default": "赛博朋克"},
            {"name": "color_scheme", "label": "配色", "type": "select",
             "options": ["蓝紫渐变", "青黑", "霓虹炫彩", "金色黑底"],
             "default": "蓝紫渐变"},
            {"name": "atmosphere", "label": "氛围", "type": "select",
             "options": ["震撼", "神秘", "高端", "活力"], "default": "震撼"},
        ],
        "default_size": "1024x1536",
    },
    {
        "id": "social_media_cover",
        "name": "社交媒体封面",
        "description": "适用于 Instagram/微信/微博等平台的封面图",
        "category": "社交媒体",
        "icon": "SHARE",
        "tags": ["社交", "封面"],
        "prompt_template": (
            "Design a social media cover image for {platform}. "
            "Content: {content_theme}. "
            "Style: {style}. Color mood: {color_mood}. "
            "Aspect ratio optimized for {platform}. "
            "Eye-catching, scroll-stopping design with clear focal point. "
            "Include subtle {element} as decorative elements."
        ),
        "variables": [
            {"name": "platform", "label": "平台", "type": "select",
             "options": ["Instagram (1:1)", "Instagram Story (9:16)",
                         "微信公众号封面", "微博封面", "小红书封面"],
             "default": "Instagram (1:1)"},
            {"name": "content_theme", "label": "内容主题", "type": "text",
             "placeholder": "如：旅行日记、美食推荐、穿搭分享", "required": True},
            {"name": "style", "label": "风格", "type": "select",
             "options": ["清新文艺", "潮流街头", "高级感", "可爱插画", "摄影风"],
             "default": "清新文艺"},
            {"name": "color_mood", "label": "色彩氛围", "type": "select",
             "options": ["明亮温暖", "冷淡高级", "粉嫩少女", "深沉质感", "彩虹活力"],
             "default": "明亮温暖"},
            {"name": "element", "label": "装饰元素", "type": "text",
             "placeholder": "如：花朵、几何图形、手绘线条",
             "required": False, "default": "几何图形"},
        ],
        "default_size": "1024x1024",
    },
    {
        "id": "logo_modern",
        "name": "现代Logo",
        "description": "简洁现代的品牌/公司 Logo 设计",
        "category": "Logo",
        "icon": "BRANDING_WATERMARK",
        "tags": ["Logo", "品牌"],
        "prompt_template": (
            "Design a modern, minimalist logo for '{brand_name}'. "
            "Industry: {industry}. "
            "Style: {style}. Colors: {colors}. "
            "The logo should be simple, memorable, and scalable. "
            "Clean lines, professional look. "
            "Background: {background}. Vector-style rendering."
        ),
        "variables": [
            {"name": "brand_name", "label": "品牌名称", "type": "text",
             "placeholder": "如：NovaTech", "required": True},
            {"name": "industry", "label": "行业", "type": "select",
             "options": ["科技", "餐饮", "教育", "时尚", "金融", "健康", "娱乐", "其他"],
             "default": "科技"},
            {"name": "style", "label": "风格", "type": "select",
             "options": ["极简", "几何", "手写体", "字母组合", "图标+文字", "抽象符号"],
             "default": "极简"},
            {"name": "colors", "label": "主色调", "type": "text",
             "placeholder": "如：深蓝+白色、黑金",
             "required": False, "default": "深蓝+白色"},
            {"name": "background", "label": "背景", "type": "select",
             "options": ["纯白", "纯黑", "透明感", "渐变"], "default": "纯白"},
        ],
        "default_size": "1024x1024",
    },
    {
        "id": "product_showcase",
        "name": "产品展示",
        "description": "电商/营销用的产品展示图",
        "category": "产品",
        "icon": "SHOPPING_BAG",
        "tags": ["电商", "产品"],
        "prompt_template": (
            "Create a professional product showcase image for '{product_name}'. "
            "Category: {category}. Style: {style}. "
            "Background: {background}. Lighting: {lighting}. "
            "The product should be the clear focal point, {angle} angle. "
            "High-end commercial photography feel. "
            "Include subtle {props} as styling props."
        ),
        "variables": [
            {"name": "product_name", "label": "产品名称", "type": "text",
             "placeholder": "如：无线降噪耳机", "required": True},
            {"name": "category", "label": "品类", "type": "select",
             "options": ["电子产品", "美妆护肤", "食品饮料", "服装配饰", "家居用品", "其他"],
             "default": "电子产品"},
            {"name": "style", "label": "拍摄风格", "type": "select",
             "options": ["白底纯净", "场景化", "暗调质感", "活力明亮", "杂志大片"],
             "default": "白底纯净"},
            {"name": "background", "label": "背景", "type": "select",
             "options": ["纯白", "大理石纹", "木纹桌面", "渐变色", "生活场景"],
             "default": "纯白"},
            {"name": "lighting", "label": "灯光", "type": "select",
             "options": ["柔和自然光", "硬光对比", "环形光", "逆光轮廓"],
             "default": "柔和自然光"},
            {"name": "angle", "label": "拍摄角度", "type": "select",
             "options": ["正面", "45度俯拍", "平视", "仰拍", "特写"],
             "default": "45度俯拍"},
            {"name": "props", "label": "搭配道具", "type": "text",
             "placeholder": "如：绿植、咖啡杯", "required": False, "default": ""},
        ],
        "default_size": "1024x1024",
    },
    {
        "id": "art_digital",
        "name": "数字艺术",
        "description": "创意数字艺术/插画作品",
        "category": "艺术",
        "icon": "PALETTE",
        "tags": ["艺术", "创意"],
        "prompt_template": (
            "Create a digital artwork depicting '{scene}'. "
            "Art style: {art_style}. Mood: {mood}. "
            "Color palette: {color_palette}. "
            "Composition: {composition}. "
            "Highly detailed, artistic, visually stunning. "
            "Inspired by {inspiration}."
        ),
        "variables": [
            {"name": "scene", "label": "画面场景", "type": "text",
             "placeholder": "如：漂浮在云端的古城", "required": True},
            {"name": "art_style", "label": "艺术风格", "type": "select",
             "options": ["赛博朋克", "水彩插画", "油画质感", "像素艺术",
                         "3D渲染", "中国风水墨", "日系动漫"],
             "default": "水彩插画"},
            {"name": "mood", "label": "氛围", "type": "select",
             "options": ["梦幻", "宁静", "壮丽", "神秘", "温馨", "暗黑"],
             "default": "梦幻"},
            {"name": "color_palette", "label": "色彩", "type": "select",
             "options": ["暖色系", "冷色系", "霓虹色", "莫兰迪", "单色", "彩虹"],
             "default": "暖色系"},
            {"name": "composition", "label": "构图", "type": "select",
             "options": ["对称构图", "三分法", "引导线", "框架构图", "极简留白"],
             "default": "三分法"},
            {"name": "inspiration", "label": "灵感来源", "type": "text",
             "placeholder": "如：宫崎骏、莫奈、AKIRA",
             "required": False, "default": ""},
        ],
        "default_size": "1024x1024",
    },
    {
        "id": "wallpaper_abstract",
        "name": "抽象壁纸",
        "description": "桌面/手机抽象艺术壁纸",
        "category": "艺术",
        "icon": "WALLPAPER",
        "tags": ["壁纸", "抽象"],
        "prompt_template": (
            "Design an abstract wallpaper for {device}. "
            "Theme: {theme}. Style: {style}. "
            "Colors: {colors}. "
            "Flowing shapes, smooth gradients, modern aesthetic. "
            "Resolution optimized for {device} screen. "
            "Visually calming, suitable as a background wallpaper."
        ),
        "variables": [
            {"name": "device", "label": "设备", "type": "select",
             "options": ["桌面电脑 (16:9)", "手机 (9:16)", "平板 (4:3)"],
             "default": "桌面电脑 (16:9)"},
            {"name": "theme", "label": "主题", "type": "text",
             "placeholder": "如：宇宙星云、海洋波浪、极光", "required": True},
            {"name": "style", "label": "风格", "type": "select",
             "options": ["流体渐变", "几何抽象", "有机形态", "故障艺术", "极简线条"],
             "default": "流体渐变"},
            {"name": "colors", "label": "配色", "type": "text",
             "placeholder": "如：深紫+青蓝、粉橙渐变",
             "required": False, "default": "深紫+青蓝"},
        ],
        "default_size": "1024x1536",
    },
    {
        "id": "food_photography",
        "name": "美食摄影",
        "description": "餐厅/美食博主专用的食物摄影",
        "category": "产品",
        "icon": "RESTAURANT",
        "tags": ["美食", "摄影"],
        "prompt_template": (
            "Create an appetizing food photograph of '{dish_name}'. "
            "Cuisine: {cuisine}. Style: {style}. "
            "Background: {background}. Lighting: {lighting}. "
            "Steam or fresh ingredients visible. "
            "Shot from {angle} angle. "
            "Professional food photography, magazine quality."
        ),
        "variables": [
            {"name": "dish_name", "label": "菜品名称", "type": "text",
             "placeholder": "如：抹茶提拉米苏", "required": True},
            {"name": "cuisine", "label": "菜系", "type": "select",
             "options": ["中餐", "日料", "西餐", "甜品", "饮品", "东南亚"],
             "default": "甜品"},
            {"name": "style", "label": "风格", "type": "select",
             "options": ["杂志大片", "家庭温馨", "暗调高级", "明亮清新", "ins网红风"],
             "default": "杂志大片"},
            {"name": "background", "label": "背景", "type": "select",
             "options": ["木桌", "大理石台面", "纯色背景", "餐厅环境", "户外自然"],
             "default": "木桌"},
            {"name": "lighting", "label": "光线", "type": "select",
             "options": ["自然窗光", "暖色灯光", "硬光投影", "柔光箱"],
             "default": "自然窗光"},
            {"name": "angle", "label": "角度", "type": "select",
             "options": ["45度俯拍", "正俯拍 (Flat Lay)", "平视", "特写"],
             "default": "45度俯拍"},
        ],
        "default_size": "1024x1024",
    },
    {
        "id": "architecture",
        "name": "建筑设计",
        "description": "建筑外观/室内设计效果图",
        "category": "艺术",
        "icon": "ARCHITECTURE",
        "tags": ["建筑", "设计"],
        "prompt_template": (
            "Visualize a {building_type} with {arch_style} architecture. "
            "Setting: {setting}. Time of day: {time}. "
            "Materials: {materials}. Mood: {mood}. "
            "Photorealistic rendering, architectural visualization quality. "
            "Professional composition with dramatic lighting."
        ),
        "variables": [
            {"name": "building_type", "label": "建筑类型", "type": "select",
             "options": ["现代别墅", "摩天大楼", "中式庭院", "教堂/寺庙",
                         "商业空间", "图书馆", "咖啡馆"],
             "default": "现代别墅"},
            {"name": "arch_style", "label": "建筑风格", "type": "select",
             "options": ["现代极简", "新中式", "哥特式", "日式枯山水",
                         "工业风", "Art Deco"],
             "default": "现代极简"},
            {"name": "setting", "label": "环境", "type": "select",
             "options": ["城市中心", "海边悬崖", "山林之间", "沙漠绿洲", "湖畔"],
             "default": "海边悬崖"},
            {"name": "time", "label": "时间", "type": "select",
             "options": ["黄金时刻 (日落)", "蓝色时刻 (黄昏)", "正午",
                         "夜晚灯光", "清晨薄雾"],
             "default": "黄金时刻 (日落)"},
            {"name": "materials", "label": "主要材质", "type": "text",
             "placeholder": "如：玻璃+混凝土+木材",
             "required": False, "default": "玻璃+混凝土"},
            {"name": "mood", "label": "氛围", "type": "select",
             "options": ["宁静", "壮观", "温馨", "神秘", "未来感"],
             "default": "宁静"},
        ],
        "default_size": "1536x1024",
    },
    {
        "id": "custom",
        "name": "自由创作",
        "description": "完全自定义你的生图提示词",
        "category": "其他",
        "icon": "EDIT_NOTE",
        "tags": ["自定义"],
        "prompt_template": "{custom_prompt}",
        "variables": [
            {"name": "custom_prompt", "label": "完整提示词", "type": "textarea",
             "placeholder": "直接输入你的生图提示词，支持中英文...", "required": True},
        ],
        "default_size": "1024x1024",
    },
]


def get_templates(category: str = "全部", keyword: str = "") -> list[dict]:
    """获取模板列表，支持分类过滤和关键词搜索。"""
    result = TEMPLATES
    if category != "全部":
        result = [t for t in result if t["category"] == category]
    if keyword:
        kw = keyword.lower()
        result = [
            t for t in result
            if kw in t["name"].lower()
            or kw in t["description"].lower()
            or any(kw in tag.lower() for tag in t["tags"])
        ]
    return result


def get_template_by_id(template_id: str) -> dict | None:
    """根据 ID 获取模板。"""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def assemble_prompt(template: dict, values: dict) -> str:
    """根据模板和用户填写的值组装完整提示词。

    - 已填字段：替换 {name} → 值
    - 未填必填字段：用 [标签] 占位，方便用户在预览区察觉缺失
    - 可选字段：用 default 兜底，空字符串直接清掉周边空格
    """
    prompt = template["prompt_template"]
    for var in template["variables"]:
        name = var["name"]
        value = values.get(name, "")
        if value == "" or value is None:
            value = var.get("default", "")
        if not value and var.get("required"):
            value = f"[{var['label']}]"
        prompt = prompt.replace(f"{{{name}}}", str(value))
    return prompt
