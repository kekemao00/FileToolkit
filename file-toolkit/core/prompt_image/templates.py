"""
内置提示词模板库

模板结构（内置、自定义、订阅源导入的模板共用）：
- id: 唯一标识（订阅源 / 自定义模板会带前缀，如 "custom:xxx"）
- name: 显示名称
- description: 简短描述
- category: 分类
- icon: 图标名称（Material Icons 枚举名，大写下划线形式）
- tags: 标签列表
- prompt_template: 提示词模板（{变量名} 为占位符）
- variables: 变量定义列表，每个包含 name, label, type, options, placeholder, required, default
- default_size: 默认图片尺寸
- source / author / link / license: 来源信息（内置模板 source="builtin"）

提示词正文用英文书写（生图模型对英文描述理解最稳定），变量值可填中文。
"""
from __future__ import annotations

BUILTIN_SOURCE = "builtin"


def _text(name: str, label: str, placeholder: str = "", required: bool = True,
          default: str = "") -> dict:
    return {"name": name, "label": label, "type": "text", "placeholder": placeholder,
            "required": required, "default": default}


def _select(name: str, label: str, options: list[str], default: str | None = None) -> dict:
    return {"name": name, "label": label, "type": "select", "options": options,
            "default": default or options[0]}


def _tpl(id_: str, name: str, description: str, category: str, icon: str,
         tags: list[str], prompt: str, variables: list[dict],
         size: str = "1024x1024") -> dict:
    return {
        "id": id_, "name": name, "description": description, "category": category,
        "icon": icon, "tags": tags, "prompt_template": prompt, "variables": variables,
        "default_size": size, "source": BUILTIN_SOURCE, "author": "", "link": "",
        "license": "",
    }


TEMPLATES: list[dict] = [
    # ── 海报设计 ───────────────────────────────────────────────────────
    _tpl(
        "poster_minimal", "简约海报", "极简留白的活动 / 宣传海报，层级清晰",
        "海报设计", "ARTICLE", ["热门", "排版"],
        "A minimalist event poster for \"{theme}\". Headline text \"{title}\" set in a "
        "refined sans-serif, secondary line \"{subtitle}\" in smaller type. Style: {style}. "
        "Color palette: {color_scheme}. Generous negative space, strict grid alignment, "
        "one strong focal graphic, clear visual hierarchy, crisp print-ready typography, "
        "all text spelled exactly as given.",
        [
            _text("theme", "主题", "如：2026 春季音乐节"),
            _text("title", "主标题", "如：春之声"),
            _text("subtitle", "副标题", "如：2026.05.20 城市音乐厅", required=False),
            _select("style", "风格", ["Swiss International Style", "Japanese wabi-sabi",
                                      "Scandinavian minimal", "Bauhaus geometric"]),
            _select("color_scheme", "配色", ["black, white and one red accent",
                                             "muted Morandi tones", "classic blue and white",
                                             "warm earth tones", "cool monochrome blue"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "poster_tech", "科技发布会海报", "未来感强烈的产品发布 / 峰会主视觉",
        "海报设计", "ROCKET_LAUNCH", ["科技", "主视觉"],
        "A futuristic key visual poster for \"{event_name}\", theme: {theme}. "
        "Visual language: {style}, {color_scheme} palette, abstract light trails, particles "
        "and holographic data streams converging on a glowing central object. Bold modern "
        "sans-serif headline \"{event_name}\" with precise kerning. Mood: {atmosphere}. "
        "High contrast, cinematic volumetric lighting, ultra sharp details.",
        [
            _text("event_name", "活动 / 产品名称", "如：AI Summit 2026"),
            _text("theme", "主题", "如：智能改变未来"),
            _select("style", "视觉风格", ["sleek cyberpunk", "holographic glassmorphism",
                                         "dark premium tech", "deep space exploration"]),
            _select("color_scheme", "配色", ["blue-violet gradient", "cyan on black",
                                            "neon multicolor", "gold on black"]),
            _select("atmosphere", "氛围", ["epic and powerful", "mysterious", "premium",
                                          "energetic"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "poster_film", "电影海报", "好莱坞院线风格的电影 / 剧集海报",
        "海报设计", "MOVIE", ["电影", "叙事"],
        "A theatrical movie poster for a {genre} film titled \"{title}\". Key art: {scene}. "
        "Dramatic cinematic lighting, strong silhouette composition, subtle film grain, "
        "{color_grade} color grading. Title in large custom lettering near the bottom, "
        "tagline \"{tagline}\" above it, small billing block at the very bottom. "
        "Professional one-sheet layout.",
        [
            _text("title", "片名", "如：长夜将尽"),
            _text("scene", "主画面", "如：雨夜霓虹街头，主角背影望向远方高楼"),
            _select("genre", "类型", ["sci-fi thriller", "romantic drama", "fantasy adventure",
                                     "crime noir", "animated family", "horror"]),
            _select("color_grade", "调色", ["teal and orange", "desaturated cold",
                                           "warm vintage", "high-contrast noir"]),
            _text("tagline", "宣传语", "如：黎明之前，最黑暗", required=False),
        ],
        "1024x1536",
    ),
    _tpl(
        "poster_chinese", "国潮海报", "新中式 / 国潮风格的节日与品牌海报",
        "海报设计", "TEMPLE_BUDDHIST", ["国风", "节日"],
        "A Chinese guochao style poster for {occasion}. Main subject: {subject}. "
        "Blend traditional elements ({elements}) with modern flat graphic design, "
        "rich {palette} palette, paper-cut layering and subtle gold foil texture. "
        "Large Chinese calligraphy headline \"{headline}\" rendered accurately, "
        "balanced asymmetric layout, festive yet refined.",
        [
            _text("occasion", "场景 / 节日", "如：中秋节、品牌周年庆"),
            _text("subject", "主体", "如：玉兔捧月饼"),
            _text("headline", "标题文字", "如：月满中秋"),
            _text("elements", "传统元素", "如：祥云、灯笼、山水", required=False,
                  default="auspicious clouds, lanterns, mountains"),
            _select("palette", "配色", ["vermilion and gold", "indigo and porcelain white",
                                       "jade green and gold", "ink black and cinnabar"]),
        ],
        "1024x1536",
    ),
    # ── 电商产品 ───────────────────────────────────────────────────────
    _tpl(
        "product_hero", "电商主图", "白底 / 场景化的商品主图，适合详情页首图",
        "电商产品", "SHOPPING_BAG", ["热门", "电商"],
        "Professional e-commerce hero shot of {product}. {style}. Background: {background}. "
        "Lighting: {lighting}. Product centered and perfectly in focus, {angle}, accurate "
        "materials and reflections, clean edges, subtle contact shadow, premium "
        "commercial photography, 8K detail. {props}",
        [
            _text("product", "产品", "如：哑光黑无线降噪耳机"),
            _select("style", "拍摄风格", ["Pure studio packshot", "Lifestyle scene styling",
                                         "Dark moody luxury look", "Bright fresh look",
                                         "Magazine editorial look"]),
            _select("background", "背景", ["seamless pure white", "soft gradient backdrop",
                                          "polished marble surface", "natural wood tabletop",
                                          "colored paper set with geometric pedestals"]),
            _select("lighting", "灯光", ["large softbox, soft and even",
                                        "hard light with crisp shadows",
                                        "rim light outlining the silhouette",
                                        "natural window light"]),
            _select("angle", "角度", ["three-quarter view", "front view", "top-down view",
                                     "low hero angle", "macro close-up"]),
            _text("props", "道具 / 补充", "如：绿植、水珠、丝绸", required=False),
        ],
    ),
    _tpl(
        "product_splash", "动感飞溅广告", "液体飞溅、食材悬浮的高冲击力广告图",
        "电商产品", "WATER_DROP", ["广告", "动感"],
        "High-speed commercial photograph of {product} surrounded by dynamic {splash} "
        "frozen in mid-air, with {ingredients} floating around it. Dramatic studio lighting, "
        "{background} background, crystal-clear droplets, shallow depth of field, "
        "ultra-detailed textures, vibrant yet realistic colors, award-winning advertising shot.",
        [
            _text("product", "产品", "如：气泡橙汁饮料瓶"),
            _select("splash", "飞溅元素", ["liquid splash", "milk crown splash", "powder explosion",
                                          "water ripples", "chocolate swirl"]),
            _text("ingredients", "悬浮食材", "如：鲜橙切片、薄荷叶、冰块"),
            _select("background", "背景色", ["deep gradient", "bright solid color",
                                            "black", "pastel"]),
        ],
    ),
    _tpl(
        "product_miniature", "微缩场景广告", "小人国微缩世界与超大产品的创意组合",
        "电商产品", "PRECISION_MANUFACTURING", ["创意", "微缩"],
        "A hyper-realistic miniature diorama advertisement: an oversized {product} stands "
        "on a circular platform while tiny figurines {activity} around it. Tilt-shift "
        "photography, soft diffused studio light, {palette} palette, meticulous tiny "
        "details (scaffolding, vehicles, props), clean seamless background, playful "
        "and premium commercial CGI render.",
        [
            _text("product", "产品", "如：护肤乳液瓶"),
            _text("activity", "小人在做什么", "如：搭脚手架给瓶身刷漆、开吊车搬运"),
            _select("palette", "色调", ["warm beige and gold", "fresh mint and white",
                                       "bold primary colors", "pastel candy colors"]),
        ],
    ),
    _tpl(
        "food_photography", "美食摄影", "餐厅菜单、外卖与美食博主的出片",
        "电商产品", "RESTAURANT", ["美食", "摄影"],
        "Appetizing professional food photograph of {dish}, {cuisine} cuisine. "
        "Styling: {style}. Surface: {background}. Lighting: {lighting}. "
        "Visible steam and fresh garnish, glossy textures, {angle}, shallow depth of field, "
        "magazine-quality food styling.",
        [
            _text("dish", "菜品", "如：抹茶提拉米苏"),
            _select("cuisine", "菜系", ["Chinese", "Japanese", "Western", "dessert",
                                       "beverage", "Southeast Asian"]),
            _select("style", "风格", ["editorial magazine", "cozy home cooking",
                                     "dark moody fine dining", "bright and airy",
                                     "trendy cafe"]),
            _select("background", "台面", ["rustic wood table", "marble countertop",
                                          "solid color backdrop", "restaurant setting"]),
            _select("lighting", "光线", ["soft window light", "warm tungsten light",
                                        "hard sunlight with shadows", "large softbox"]),
            _select("angle", "角度", ["45-degree angle", "overhead flat lay", "eye level",
                                     "macro close-up"]),
        ],
    ),
    # ── 摄影写真 ───────────────────────────────────────────────────────
    _tpl(
        "portrait_studio", "影棚人像", "专业棚拍人像 / 形象照 / 头像",
        "摄影写真", "PORTRAIT", ["人像", "形象照"],
        "Professional studio portrait of {subject}, wearing {outfit}, {expression}. "
        "{lighting}, {background} backdrop, shot on 85mm lens at f/1.8, natural skin texture, "
        "sharp eyes, subtle retouching, editorial quality.",
        [
            _text("subject", "人物", "如：30 岁亚洲女性产品经理，短发"),
            _text("outfit", "服装", "如：米色西装外套", required=False,
                  default="smart casual clothing"),
            _select("expression", "表情姿态", ["confident gentle smile", "serious and focused",
                                              "candid laughing", "thoughtful side glance"]),
            _select("lighting", "布光", ["Rembrandt lighting", "soft butterfly lighting",
                                        "clamshell beauty lighting", "low-key dramatic lighting"]),
            _select("background", "背景", ["neutral gray", "warm beige", "deep navy",
                                          "pure white", "textured canvas"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "portrait_film", "胶片写真", "复古胶片质感的街拍 / 旅行写真",
        "摄影写真", "CAMERA_ROLL", ["胶片", "氛围"],
        "Candid film photograph of {subject} at {location}, {time}. Shot on {film}, "
        "35mm lens, natural grain, slight halation, authentic color shifts, "
        "unposed moment, nostalgic cinematic atmosphere.",
        [
            _text("subject", "人物 / 主体", "如：穿白裙的女孩骑单车"),
            _text("location", "地点", "如：海边公路、京都小巷"),
            _select("time", "时间", ["golden hour", "blue hour", "overcast afternoon",
                                    "night with neon lights"]),
            _select("film", "胶片", ["Kodak Portra 400", "Fujifilm Superia 400",
                                    "Kodak Gold 200", "CineStill 800T", "Ilford HP5 black and white"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "landscape_photo", "风光摄影", "国家地理风格的自然风光大片",
        "摄影写真", "LANDSCAPE", ["风景", "大片"],
        "Breathtaking landscape photograph of {place}, {weather}, {time}. "
        "Foreground {foreground} leading into the scene, layered depth, {lens}, "
        "long exposure where appropriate, rich dynamic range, National Geographic quality.",
        [
            _text("place", "地点", "如：冰岛黑沙滩、稻城亚丁"),
            _select("weather", "天气", ["dramatic clouds", "light mist", "clear sky",
                                       "aurora in the sky", "after-rain clarity"]),
            _select("time", "时间", ["sunrise", "golden hour sunset", "blue hour",
                                    "starry night with milky way"]),
            _text("foreground", "前景", "如：岩石与溪流", required=False,
                  default="textured rocks"),
            _select("lens", "镜头", ["ultra wide-angle 16mm", "telephoto compression 200mm",
                                    "panoramic composition"]),
        ],
        "1536x1024",
    ),
    _tpl(
        "pet_photo", "萌宠写真", "宠物肖像、表情包与创意宠物照",
        "摄影写真", "PETS", ["宠物", "可爱"],
        "Adorable photo of {pet}, {action}, in {scene}. {style}, eye-level shot, "
        "sharp focus on the eyes, soft fur details, warm natural light, joyful mood.",
        [
            _text("pet", "宠物", "如：橘色英短猫"),
            _text("action", "动作", "如：戴着小厨师帽偷吃饼干"),
            _text("scene", "场景", "如：温馨厨房"),
            _select("style", "风格", ["Professional pet photography", "Studio portrait",
                                     "Pixar-like 3D render", "Watercolor illustration"]),
        ],
    ),
    # ── 插画艺术 ───────────────────────────────────────────────────────
    _tpl(
        "art_digital", "数字插画", "概念感强的数字艺术 / 插画作品",
        "插画艺术", "PALETTE", ["艺术", "创意"],
        "A digital illustration of {scene}. Art style: {art_style}. Mood: {mood}. "
        "Color palette: {color_palette}. Composition: {composition}. "
        "Highly detailed, painterly brushwork, cohesive lighting. {inspiration}",
        [
            _text("scene", "画面场景", "如：漂浮在云端的古城"),
            _select("art_style", "艺术风格", ["Studio Ghibli-inspired anime", "watercolor",
                                             "impasto oil painting", "pixel art",
                                             "cel-shaded comic", "Chinese ink wash painting",
                                             "concept art matte painting"]),
            _select("mood", "氛围", ["dreamy", "serene", "epic", "mysterious", "cozy", "dark"]),
            _select("color_palette", "色彩", ["warm tones", "cool tones", "neon",
                                             "Morandi muted", "monochrome", "vivid rainbow"]),
            _select("composition", "构图", ["rule of thirds", "symmetrical", "leading lines",
                                           "frame within a frame", "minimal negative space"]),
            _text("inspiration", "补充描述", "如：受宫崎骏启发", required=False),
        ],
    ),
    _tpl(
        "children_book", "绘本插画", "温暖可爱的儿童绘本跨页",
        "插画艺术", "MENU_BOOK", ["绘本", "儿童"],
        "A children's picture book illustration: {story}. Soft {medium} texture, "
        "rounded friendly characters with expressive faces, warm gentle palette, "
        "storybook composition with room for text at the {text_area}, whimsical details, "
        "heartwarming mood.",
        [
            _text("story", "画面故事", "如：小狐狸和刺猬在森林里分享苹果"),
            _select("medium", "画材", ["watercolor and colored pencil", "gouache",
                                      "crayon", "digital soft brush"]),
            _select("text_area", "留白位置", ["top", "bottom", "left side", "right side"]),
        ],
        "1536x1024",
    ),
    _tpl(
        "ink_painting", "水墨国画", "中国传统水墨 / 工笔意境画",
        "插画艺术", "BRUSH", ["国风", "水墨"],
        "Traditional Chinese {technique} painting of {subject}. Expressive brush strokes, "
        "ink gradations from deep black to pale gray, {color}, rice paper texture, "
        "poetic negative space, red seal stamp in the corner, elegant and timeless.",
        [
            _text("subject", "题材", "如：烟雨江南小桥流水"),
            _select("technique", "技法", ["xieyi freehand ink", "gongbi fine-line",
                                         "blue-green landscape", "splash ink"]),
            _select("color", "设色", ["pure ink only", "light color washes",
                                     "touches of vermilion", "mineral blue and green"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "sticker_set", "贴纸表情包", "一组风格统一的贴纸 / 表情",
        "插画艺术", "EMOJI_EMOTIONS", ["表情包", "贴纸"],
        "A sticker sheet of {count} cute stickers featuring {character}, each showing a "
        "different emotion or action ({emotions}). {style}, thick white die-cut border, "
        "consistent character design, flat bright colors, evenly spaced grid on a plain "
        "background.",
        [
            _text("character", "角色", "如：一只戴眼镜的柴犬"),
            _select("count", "数量", ["6", "9", "12", "16"], "9"),
            _text("emotions", "表情 / 动作", "如：开心、生气、比心、加油、睡觉",
                  required=False, default="happy, angry, love, cheering, sleepy, surprised"),
            _select("style", "风格", ["Kawaii chibi style", "Flat vector style",
                                     "3D clay style", "Hand-drawn doodle style"]),
        ],
    ),
    # ── 品牌 Logo ──────────────────────────────────────────────────────
    _tpl(
        "logo_modern", "现代 Logo", "简洁、可识别、可缩放的品牌标志",
        "品牌 Logo", "BRANDING_WATERMARK", ["Logo", "品牌"],
        "A modern logo design for \"{brand_name}\", a {industry} brand. Style: {style}. "
        "Colors: {colors}. Simple, memorable, scalable mark with balanced negative space, "
        "precise geometry, vector-style flat rendering, brand name set in a clean "
        "typeface, centered on a {background} background. No mockup, no extra text.",
        [
            _text("brand_name", "品牌名称", "如：NovaTech"),
            _select("industry", "行业", ["technology", "food and beverage", "education",
                                        "fashion", "finance", "healthcare", "entertainment"]),
            _select("style", "风格", ["minimal line mark", "geometric symbol", "lettermark",
                                     "emblem badge", "abstract symbol with wordmark",
                                     "hand-lettered script"]),
            _text("colors", "主色调", "如：深蓝 + 白色", required=False,
                  default="deep blue and white"),
            _select("background", "背景", ["pure white", "pure black", "light gray"]),
        ],
    ),
    _tpl(
        "brand_vi", "品牌 VI 展示", "名片、包装、手提袋等品牌物料全家福",
        "品牌 Logo", "STYLE", ["VI", "样机"],
        "A brand identity presentation board for \"{brand_name}\" ({industry}). "
        "Neatly arranged mockups: business cards, letterhead, packaging box, tote bag, "
        "mobile app screen and signage, all using a consistent {style} visual system with "
        "{colors} colors. Top-down flat lay on a {surface}, soft shadows, professional "
        "design portfolio photography.",
        [
            _text("brand_name", "品牌名称", "如：森野咖啡"),
            _text("industry", "行业", "如：精品咖啡馆"),
            _select("style", "视觉风格", ["minimal modern", "warm organic", "bold playful",
                                         "luxury classic"]),
            _text("colors", "品牌色", "如：森林绿 + 奶油白"),
            _select("surface", "台面", ["light concrete surface", "linen fabric",
                                       "warm wood desk", "solid color paper"]),
        ],
        "1536x1024",
    ),
    # ── 3D 与图标 ──────────────────────────────────────────────────────
    _tpl(
        "icon_3d", "3D 图标", "柔和材质的 3D 应用图标 / 功能图标",
        "3D 与图标", "VIEW_IN_AR", ["图标", "3D"],
        "A single 3D icon of {object}, {material} material, soft rounded shapes, "
        "{palette} colors, gentle studio lighting with soft shadow, isometric "
        "three-quarter view, centered on a plain {background} background, "
        "clean high-quality render suitable for app UI.",
        [
            _text("object", "图标内容", "如：带闪电的文件夹"),
            _select("material", "材质", ["glossy plastic", "frosted glass", "soft clay",
                                        "brushed metal", "inflatable vinyl", "plush fabric"]),
            _text("palette", "配色", "如：蓝紫渐变", required=False,
                  default="blue and purple gradient"),
            _select("background", "背景", ["white", "light gray", "transparent-looking pale"]),
        ],
    ),
    _tpl(
        "chibi_figure", "Q 版手办", "潮玩手办 / 盲盒公仔效果",
        "3D 与图标", "TOYS", ["手办", "潮玩"],
        "A chibi collectible vinyl figure of {character}, big head small body proportions, "
        "{outfit}, holding {prop}. Glossy painted finish, standing on a round display base, "
        "next to its {packaging}. Soft studio lighting, product photography, "
        "pop mart blind box aesthetic.",
        [
            _text("character", "角色", "如：穿汉服的女孩"),
            _text("outfit", "服装", "如：红色斗篷", required=False, default="signature outfit"),
            _text("prop", "手持道具", "如：糖葫芦", required=False, default="a small prop"),
            _select("packaging", "包装", ["illustrated blind box packaging",
                                         "clear window display box", "no packaging"]),
        ],
    ),
    _tpl(
        "isometric_room", "等距微缩场景", "2.5D 等距视角的房间 / 建筑小场景",
        "3D 与图标", "HOLIDAY_VILLAGE", ["等距", "微缩"],
        "A cute isometric 3D miniature of {scene}, cut-away diorama on a floating square "
        "base, highly detailed tiny furniture and objects, {style}, soft global "
        "illumination, {palette} palette, clean solid background.",
        [
            _text("scene", "场景", "如：程序员的深夜书房"),
            _select("style", "风格", ["Blender low-poly", "soft clay render",
                                     "voxel style", "realistic miniature"]),
            _select("palette", "色调", ["warm cozy", "pastel", "cool night", "vivid"]),
        ],
    ),
    # ── 社交媒体 ───────────────────────────────────────────────────────
    _tpl(
        "xiaohongshu_cover", "小红书封面", "吸睛的笔记封面，大字标题 + 主体图",
        "社交媒体", "AUTO_STORIES", ["热门", "小红书"],
        "A Xiaohongshu (RED) note cover image about {topic}. Large bold Chinese headline "
        "\"{headline}\" rendered accurately, {style} design, eye-catching {palette} colors, "
        "playful stickers and highlight marks, main visual: {visual}. Vertical 3:4 "
        "layout, scroll-stopping, clean and trendy.",
        [
            _text("topic", "笔记主题", "如：周末露营好物"),
            _text("headline", "封面大字", "如：露营新手必看清单"),
            _text("visual", "主体画面", "如：帐篷与咖啡壶", required=False,
                  default="a relevant product flat lay"),
            _select("style", "风格", ["cute hand-drawn", "minimal magazine",
                                     "bold contrast", "film photo collage"]),
            _select("palette", "配色", ["cream and pink", "fresh green", "bright yellow",
                                       "black white red"]),
        ],
        "1024x1536",
    ),
    _tpl(
        "social_media_cover", "公众号 / 视频封面", "公众号头图、B 站 / YouTube 视频封面",
        "社交媒体", "SMART_DISPLAY", ["封面", "视频"],
        "A {platform} cover image about {topic}. Bold readable title \"{title}\" with "
        "strong contrast, {style}, expressive focal subject, clear visual hierarchy, "
        "high click-through thumbnail design.",
        [
            _select("platform", "平台", ["WeChat article header (2.35:1)",
                                        "YouTube thumbnail (16:9)", "Bilibili cover (16:9)"]),
            _text("topic", "内容主题", "如：三分钟学会 PDF 合并"),
            _text("title", "标题文字", "如：PDF 合并只要 3 秒"),
            _select("style", "风格", ["clean tech style", "vibrant pop style",
                                     "cinematic photo style", "flat illustration style"]),
        ],
        "1536x1024",
    ),
    # ── 建筑空间 ───────────────────────────────────────────────────────
    _tpl(
        "architecture", "建筑效果图", "建筑外观的写实可视化渲染",
        "建筑空间", "ARCHITECTURE", ["建筑", "渲染"],
        "Architectural visualization of a {building_type} in {arch_style} style, located "
        "{setting}, at {time}. Materials: {materials}. Photorealistic rendering, accurate "
        "proportions, people for scale, lush landscaping, dramatic sky, award-winning "
        "architecture photography.",
        [
            _select("building_type", "建筑类型", ["modern villa", "skyscraper",
                                                 "Chinese courtyard house", "museum",
                                                 "library", "boutique cafe"]),
            _select("arch_style", "建筑风格", ["contemporary minimalist", "new Chinese",
                                              "brutalist", "Japanese", "industrial",
                                              "parametric futuristic"]),
            _select("setting", "环境", ["on a seaside cliff", "in a dense city center",
                                       "in a misty forest", "by a calm lake",
                                       "in the desert"]),
            _select("time", "时间", ["golden hour", "blue hour with interior lights",
                                    "bright noon", "early morning fog"]),
            _text("materials", "主要材质", "如：玻璃 + 清水混凝土 + 木格栅", required=False,
                  default="glass, concrete and timber"),
        ],
        "1536x1024",
    ),
    _tpl(
        "interior_design", "室内设计", "家装 / 商业空间室内效果图",
        "建筑空间", "CHAIR", ["室内", "家装"],
        "Interior design rendering of a {room} in {style} style. {palette} palette, "
        "materials: {materials}. Natural daylight through large windows, carefully styled "
        "decor, realistic textures, wide-angle architectural photography, "
        "magazine-quality interior shot.",
        [
            _select("room", "空间", ["living room", "bedroom", "kitchen", "home office",
                                    "cafe", "hotel lobby", "bathroom"]),
            _select("style", "风格", ["Japandi", "modern minimalist", "Scandinavian",
                                     "mid-century modern", "new Chinese", "wabi-sabi",
                                     "French cream style"]),
            _text("palette", "配色", "如：原木 + 奶白", required=False,
                  default="warm neutral"),
            _text("materials", "材质", "如：橡木地板、微水泥墙面", required=False,
                  default="oak wood, linen, stone"),
        ],
        "1536x1024",
    ),
    # ── 角色设计 ───────────────────────────────────────────────────────
    _tpl(
        "character_sheet", "角色设定图", "游戏 / 动画角色三视图设定",
        "角色设计", "PERSON", ["角色", "设定"],
        "A professional character design sheet of {character}. Front, side and back "
        "turnaround views plus three facial expressions, {style}, consistent "
        "proportions, outfit details callouts, color palette swatches, clean light "
        "background, concept art presentation.",
        [
            _text("character", "角色描述", "如：银发少年剑士，身披蓝色风衣"),
            _select("style", "风格", ["anime cel shading", "semi-realistic game art",
                                     "Western cartoon", "3D stylized render"]),
        ],
        "1536x1024",
    ),
    _tpl(
        "avatar", "个性头像", "社交头像，多种艺术风格",
        "角色设计", "FACE", ["头像"],
        "A profile avatar of {subject}, {style}, head and shoulders, centered, "
        "{background} background, expressive and polished, high detail.",
        [
            _text("subject", "人物 / 角色", "如：戴耳机的短发女孩"),
            _select("style", "风格", ["Pixar-like 3D", "anime", "flat vector",
                                     "oil painting portrait", "pixel art", "clay figure"]),
            _select("background", "背景", ["solid pastel", "gradient", "simple pattern"]),
        ],
    ),
    # ── 信息图 ─────────────────────────────────────────────────────────
    _tpl(
        "infographic", "信息图卡片", "知识科普、流程说明的信息图",
        "信息图", "INSIGHTS", ["信息图", "知识"],
        "A clean infographic card explaining \"{topic}\". Sections: {points}. "
        "{style}, clear icons for each section, numbered flow, readable "
        "{language} labels rendered accurately, {palette} palette, organized grid, "
        "plenty of whitespace.",
        [
            _text("topic", "主题", "如：如何保护眼睛"),
            _text("points", "要点（逗号分隔）", "如：20-20-20 法则, 调亮度, 多眨眼, 定期检查"),
            _select("style", "风格", ["flat vector", "hand-drawn sketchnote",
                                     "isometric 3D", "minimal line art"]),
            _select("language", "文字语言", ["Chinese", "English"]),
            _select("palette", "配色", ["blue and teal", "warm orange", "pastel multicolor",
                                       "black and yellow"]),
        ],
        "1024x1536",
    ),
    # ── 壁纸背景 ───────────────────────────────────────────────────────
    _tpl(
        "wallpaper_abstract", "抽象壁纸", "桌面 / 手机抽象艺术壁纸",
        "壁纸背景", "WALLPAPER", ["壁纸", "抽象"],
        "An abstract wallpaper, theme: {theme}. Style: {style}. Colors: {colors}. "
        "Smooth flowing forms, subtle grain, calm balanced composition with no text, "
        "ultra high resolution, suitable as a {device} background.",
        [
            _text("theme", "主题", "如：宇宙星云、海浪、极光"),
            _select("style", "风格", ["fluid gradient", "geometric abstraction",
                                     "organic shapes", "glitch art", "minimal lines",
                                     "3D glass shapes"]),
            _text("colors", "配色", "如：深紫 + 青蓝", required=False,
                  default="deep purple and cyan"),
            _select("device", "设备", ["desktop", "phone", "tablet"]),
        ],
        "1536x1024",
    ),
    _tpl(
        "ppt_background", "PPT 背景", "留白充足的演示文稿背景图",
        "壁纸背景", "SLIDESHOW", ["办公", "背景"],
        "A presentation slide background for a {topic} deck. {style}, {palette} palette, "
        "decorative elements kept to the {side}, large clean empty area for text, "
        "subtle and professional, no text.",
        [
            _text("topic", "演示主题", "如：年度财务报告"),
            _select("style", "风格", ["corporate minimal", "tech gradient",
                                     "soft watercolor", "geometric lines"]),
            _select("palette", "配色", ["navy and white", "blue and green",
                                       "warm neutrals", "black and gold"]),
            _select("side", "装饰位置", ["edges", "right side", "bottom", "corners"]),
        ],
        "1536x1024",
    ),
    # ── 自由创作 ───────────────────────────────────────────────────────
    _tpl(
        "custom", "自由创作", "完全自定义你的生图提示词",
        "自由创作", "EDIT_NOTE", ["自定义"],
        "{custom_prompt}",
        [
            {"name": "custom_prompt", "label": "完整提示词", "type": "textarea",
             "placeholder": "直接输入你的生图提示词，支持中英文...", "required": True},
        ],
    ),
]

# 内置分类顺序（"全部"排在最前，用于 UI 过滤栏）
CATEGORIES = ["全部"] + list(dict.fromkeys(t["category"] for t in TEMPLATES))


def get_templates(category: str = "全部", keyword: str = "",
                  templates: list[dict] | None = None) -> list[dict]:
    """获取模板列表，支持分类过滤和关键词搜索。"""
    result = TEMPLATES if templates is None else templates
    if category and category != "全部":
        result = [t for t in result if t.get("category") == category]
    if keyword:
        kw = keyword.lower()
        result = [
            t for t in result
            if kw in t["name"].lower()
            or kw in (t.get("description") or "").lower()
            or any(kw in tag.lower() for tag in t.get("tags", []))
            or kw in (t.get("author") or "").lower()
            or kw in (t.get("prompt_template") or "").lower()
        ]
    return result


def get_template_by_id(template_id: str) -> dict | None:
    """根据 ID 获取内置模板。"""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def assemble_prompt(template: dict, values: dict) -> str:
    """根据模板和用户填写的值组装完整提示词。

    - 已填字段：替换 {name} → 值
    - 未填必填字段：用 [标签] 占位，方便用户在预览区察觉缺失
    - 可选字段：用 default 兜底，空值时顺带清理多余空格
    """
    prompt = template["prompt_template"]
    for var in template.get("variables", []):
        name = var["name"]
        value = values.get(name, "")
        if value == "" or value is None:
            value = var.get("default", "")
        if not value and var.get("required"):
            value = f"[{var['label']}]"
        prompt = prompt.replace(f"{{{name}}}", str(value))
    # 可选字段留空后可能剩下 `""`、连续空格、孤立句点
    prompt = prompt.replace('""', "").replace("  ", " ").replace(" .", ".")
    return prompt.strip()
