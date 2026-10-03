"""内置模板下拉选项的中文显示名。

提示词里写入英文选项值（生图模型理解更稳定），界面上显示这里的中文；
没登记的选项原样显示。
"""
from __future__ import annotations

OPTION_LABELS: dict[str, str] = {
    # 风格 / 设计流派
    "Swiss International Style": "瑞士国际主义", "Japanese wabi-sabi": "日式侘寂",
    "Scandinavian minimal": "北欧极简", "Bauhaus geometric": "包豪斯几何",
    "sleek cyberpunk": "赛博朋克", "holographic glassmorphism": "全息玻璃拟态",
    "dark premium tech": "暗黑高级科技", "deep space exploration": "深空探索",
    "Pure studio packshot": "白底棚拍", "Lifestyle scene styling": "生活场景",
    "Dark moody luxury look": "暗调奢华", "Bright fresh look": "明亮清新",
    "Magazine editorial look": "杂志大片", "editorial magazine": "杂志大片",
    "cozy home cooking": "家常温馨", "dark moody fine dining": "暗调高级餐厅",
    "bright and airy": "明亮通透", "trendy cafe": "网红咖啡馆",
    "Professional pet photography": "专业宠物摄影", "Studio portrait": "影棚肖像",
    "Pixar-like 3D render": "皮克斯风 3D", "Watercolor illustration": "水彩插画",
    "Studio Ghibli-inspired anime": "吉卜力风动画", "watercolor": "水彩",
    "impasto oil painting": "厚涂油画", "pixel art": "像素艺术", "cel-shaded comic": "赛璐璐漫画",
    "Chinese ink wash painting": "中国水墨", "concept art matte painting": "概念艺术绘景",
    "watercolor and colored pencil": "水彩 + 彩铅", "gouache": "水粉", "crayon": "蜡笔",
    "digital soft brush": "数字柔笔刷",
    "xieyi freehand ink": "写意水墨", "gongbi fine-line": "工笔", "blue-green landscape": "青绿山水",
    "splash ink": "泼墨", "pure ink only": "纯水墨", "light color washes": "淡彩",
    "touches of vermilion": "点缀朱红", "mineral blue and green": "石青石绿",
    "Kawaii chibi style": "日系 Q 版", "Flat vector style": "扁平矢量", "3D clay style": "3D 黏土",
    "Hand-drawn doodle style": "手绘涂鸦",
    "minimal line mark": "极简线条标", "geometric symbol": "几何图形", "lettermark": "字母组合",
    "emblem badge": "徽章", "abstract symbol with wordmark": "抽象图形 + 文字",
    "hand-lettered script": "手写字体",
    "minimal modern": "现代极简", "warm organic": "温暖自然", "bold playful": "大胆活泼",
    "luxury classic": "经典奢华",
    "Blender low-poly": "低多边形", "soft clay render": "柔和黏土", "voxel style": "体素风",
    "realistic miniature": "写实微缩",
    "cute hand-drawn": "可爱手绘", "minimal magazine": "极简杂志", "bold contrast": "强对比",
    "film photo collage": "胶片拼贴",
    "clean tech style": "简洁科技", "vibrant pop style": "活力波普", "cinematic photo style": "电影感摄影",
    "flat illustration style": "扁平插画",
    "contemporary minimalist": "当代极简", "new Chinese": "新中式", "brutalist": "粗野主义",
    "Japanese": "日式", "industrial": "工业风", "parametric futuristic": "参数化未来",
    "Japandi": "日式北欧", "modern minimalist": "现代极简", "Scandinavian": "北欧",
    "mid-century modern": "中古风", "wabi-sabi": "侘寂", "French cream style": "法式奶油",
    "anime cel shading": "动漫赛璐璐", "semi-realistic game art": "半写实游戏",
    "Western cartoon": "美式卡通", "3D stylized render": "3D 风格化",
    "Pixar-like 3D": "皮克斯风 3D", "anime": "动漫", "flat vector": "扁平矢量",
    "oil painting portrait": "油画肖像", "clay figure": "黏土人偶",
    "hand-drawn sketchnote": "手绘笔记", "isometric 3D": "等距 3D", "minimal line art": "极简线稿",
    "fluid gradient": "流体渐变", "geometric abstraction": "几何抽象", "organic shapes": "有机形态",
    "glitch art": "故障艺术", "minimal lines": "极简线条", "3D glass shapes": "3D 玻璃形体",
    "corporate minimal": "商务极简", "tech gradient": "科技渐变", "soft watercolor": "柔和水彩",
    "geometric lines": "几何线条",
    # 配色
    "black, white and one red accent": "黑白 + 一点红", "muted Morandi tones": "莫兰迪色",
    "classic blue and white": "经典蓝白", "warm earth tones": "暖大地色",
    "cool monochrome blue": "冷调单色蓝", "blue-violet gradient": "蓝紫渐变", "cyan on black": "青黑",
    "neon multicolor": "霓虹多彩", "gold on black": "黑金",
    "teal and orange": "青橙", "desaturated cold": "低饱和冷调", "warm vintage": "暖调复古",
    "high-contrast noir": "高反差黑白",
    "vermilion and gold": "朱红 + 金", "indigo and porcelain white": "靛蓝 + 瓷白",
    "jade green and gold": "翡翠绿 + 金", "ink black and cinnabar": "墨黑 + 朱砂",
    "deep gradient": "深色渐变", "bright solid color": "明亮纯色", "black": "黑色", "pastel": "马卡龙色",
    "warm beige and gold": "暖米 + 金", "fresh mint and white": "薄荷 + 白",
    "bold primary colors": "鲜明三原色", "pastel candy colors": "糖果色",
    "warm tones": "暖色系", "cool tones": "冷色系", "neon": "霓虹", "Morandi muted": "莫兰迪",
    "monochrome": "单色", "vivid rainbow": "彩虹", "warm cozy": "暖调温馨", "cool night": "冷调夜景",
    "vivid": "鲜艳", "cream and pink": "奶油粉", "fresh green": "清新绿", "bright yellow": "明黄",
    "black white red": "黑白红", "blue and teal": "蓝 + 青", "warm orange": "暖橙",
    "pastel multicolor": "柔和多彩", "black and yellow": "黑黄", "navy and white": "藏青 + 白",
    "blue and green": "蓝绿", "warm neutrals": "暖中性色", "black and gold": "黑金",
    # 氛围
    "epic and powerful": "震撼", "mysterious": "神秘", "premium": "高端", "energetic": "活力",
    "dreamy": "梦幻", "serene": "宁静", "epic": "壮丽", "cozy": "温馨", "dark": "暗黑",
    # 电影类型
    "sci-fi thriller": "科幻惊悚", "romantic drama": "爱情", "fantasy adventure": "奇幻冒险",
    "crime noir": "犯罪黑色", "animated family": "合家欢动画", "horror": "恐怖",
    # 背景 / 台面
    "seamless pure white": "纯白无缝", "soft gradient backdrop": "柔和渐变",
    "polished marble surface": "大理石台面", "natural wood tabletop": "原木桌面",
    "colored paper set with geometric pedestals": "彩色背景纸 + 几何展台",
    "rustic wood table": "复古木桌", "marble countertop": "大理石台面",
    "solid color backdrop": "纯色背景", "restaurant setting": "餐厅环境",
    "neutral gray": "中性灰", "warm beige": "暖米色", "deep navy": "深藏青", "pure white": "纯白",
    "textured canvas": "肌理画布", "pure black": "纯黑", "light gray": "浅灰", "white": "白色",
    "transparent-looking pale": "近透明浅色",
    "light concrete surface": "浅色水泥", "linen fabric": "亚麻布", "warm wood desk": "暖色木桌",
    "solid color paper": "纯色卡纸", "solid pastel": "纯色马卡龙", "gradient": "渐变",
    "simple pattern": "简单图案",
    # 灯光
    "large softbox, soft and even": "大柔光箱 · 柔和均匀", "hard light with crisp shadows": "硬光 · 清晰投影",
    "rim light outlining the silhouette": "轮廓光", "natural window light": "自然窗光",
    "soft window light": "柔和窗光", "warm tungsten light": "暖色钨丝灯",
    "hard sunlight with shadows": "硬朗阳光", "large softbox": "大柔光箱",
    "Rembrandt lighting": "伦勃朗光", "soft butterfly lighting": "蝴蝶光",
    "clamshell beauty lighting": "蚌壳美颜光", "low-key dramatic lighting": "低调戏剧光",
    # 角度 / 镜头
    "three-quarter view": "四分之三侧", "front view": "正面", "top-down view": "俯视",
    "low hero angle": "低角度仰拍", "macro close-up": "微距特写", "45-degree angle": "45 度",
    "overhead flat lay": "正俯拍平铺", "eye level": "平视",
    "ultra wide-angle 16mm": "超广角 16mm", "telephoto compression 200mm": "长焦压缩 200mm",
    "panoramic composition": "全景构图",
    "rule of thirds": "三分法", "symmetrical": "对称", "leading lines": "引导线",
    "frame within a frame": "框中框", "minimal negative space": "极简留白",
    # 表情
    "confident gentle smile": "自信微笑", "serious and focused": "专注严肃", "candid laughing": "自然大笑",
    "thoughtful side glance": "侧目沉思",
    # 时间 / 天气
    "golden hour": "黄金时刻", "blue hour": "蓝调时刻", "overcast afternoon": "阴天午后",
    "night with neon lights": "霓虹夜晚", "sunrise": "日出", "golden hour sunset": "日落",
    "starry night with milky way": "银河星空", "blue hour with interior lights": "黄昏亮灯",
    "bright noon": "正午", "early morning fog": "清晨薄雾",
    "dramatic clouds": "戏剧云层", "light mist": "薄雾", "clear sky": "晴空", "aurora in the sky": "极光",
    "after-rain clarity": "雨后通透",
    # 胶片
    "Ilford HP5 black and white": "Ilford HP5 黑白",
    # 飞溅
    "liquid splash": "液体飞溅", "milk crown splash": "牛奶皇冠", "powder explosion": "粉末爆炸",
    "water ripples": "水波纹", "chocolate swirl": "巧克力漩涡",
    # 菜系
    "Chinese": "中餐", "Western": "西餐", "dessert": "甜品", "beverage": "饮品",
    "Southeast Asian": "东南亚",
    # 行业
    "technology": "科技", "food and beverage": "餐饮", "education": "教育", "fashion": "时尚",
    "finance": "金融", "healthcare": "医疗健康", "entertainment": "娱乐",
    # 材质
    "glossy plastic": "亮面塑料", "frosted glass": "磨砂玻璃", "soft clay": "软黏土",
    "brushed metal": "拉丝金属", "inflatable vinyl": "充气膜", "plush fabric": "毛绒",
    # 包装
    "illustrated blind box packaging": "插画盲盒包装", "clear window display box": "透明开窗盒",
    "no packaging": "无包装",
    # 平台
    "WeChat article header (2.35:1)": "公众号头图 (2.35:1)", "YouTube thumbnail (16:9)": "YouTube 封面 (16:9)",
    "Bilibili cover (16:9)": "B 站封面 (16:9)",
    # 建筑 / 空间
    "modern villa": "现代别墅", "skyscraper": "摩天大楼", "Chinese courtyard house": "中式庭院",
    "museum": "博物馆", "library": "图书馆", "boutique cafe": "精品咖啡馆",
    "on a seaside cliff": "海边悬崖", "in a dense city center": "城市中心", "in a misty forest": "雾中森林",
    "by a calm lake": "湖畔", "in the desert": "沙漠",
    "living room": "客厅", "bedroom": "卧室", "kitchen": "厨房", "home office": "书房",
    "cafe": "咖啡馆", "hotel lobby": "酒店大堂", "bathroom": "卫浴",
    # 位置 / 设备 / 语言
    "top": "顶部", "bottom": "底部", "left side": "左侧", "right side": "右侧",
    "edges": "四周", "corners": "四角", "desktop": "电脑", "phone": "手机", "tablet": "平板",
    "English": "英文",
}


def option_label(value: str) -> str:
    return OPTION_LABELS.get(value, value)
