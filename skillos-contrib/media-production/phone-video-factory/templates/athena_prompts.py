"""
Phone Video Factory — Athena 角色视频模板

PENTA 五层提示词模板，适配各平台 AI 视频生成。
"""

# 角色参考图路径 (用于 I2V 模式)
# 通过环境变量或运行时参数配置
DEFAULT_REF_IMAGE = os.environ.get(
    "PHONE_VIDEO_REF_IMAGE",
    "./assets/character_ref.jpg"
)

# ============ 文生视频 (T2V) 模板 ============

ATHENA_T2V_PORTRAIT = (
    "一位银发女性AI角色Athena，冰蓝色发光眼睛，"
    "碳纤维外骨骼上有淡蓝色能量脉络，"
    "胸口有六边形核心，微弱呼吸光芒，"
    "背景是未来城市的全息投影界面，"
    "电影质感，photorealistic，皮肤 sub-surface scattering，"
    "浅景深，ambient occlusion，8K质量"
)

ATHENA_T2V_CLOSEUP = (
    "银发女性AI角色Athena的面部特写，"
    "冰蓝色双眼中有流动的数据流光芒，"
    "皮肤有微小的碳纤维纹理，sub-surface scattering，"
    "脸部微微倾斜，表现出专注思考的表情，"
    "cinematic lighting，shallow depth of field，"
    "电影质感，photorealistic"
)

ATHENA_T2V_FULLBODY = (
    "银发女性AI角色Athena全身站立姿态，"
    "body-on 碳纤维外骨骼，冰蓝色能量脉络流动，"
    "身体姿态优雅而有力，"
    "身后是巨大的全息投影屏幕显示数据流，"
    "低角度镜头，仰视构图，cinematic lighting，"
    "photorealistic，8K"
)

# ============ 图生视频 (I2V) 模板 ============

ATHENA_I2V_BASE = (
    "银发女性AI角色Athena，保持与参考图一致的角色外观，"
    "冰蓝色眼睛，碳纤维外骨骼，"
    "自然的头部微动，眼睛有光芒闪烁，"
    "头发微微飘动，背景保持稳定，"
    "cinematic quality，smooth motion，"
    "no morphing artifacts，consistent character"
)

ATHENA_I2V_TALKING = (
    "银发女性AI角色Athena，保持角色一致性，"
    "嘴部自然张合，如同在说话，"
    "头部轻微倾斜和点头，"
    "眼睛中有数据流光芒在动，"
    "portrait framing，natural speech gestures，"
    "stable background，no face distortion"
)

# ============ 通用模板 ============

GENERIC_T2V = (
    "cinematic quality，photorealistic，"
    "smooth camera movement，8K resolution，"
    "professional lighting，shallow depth of field，"
    "no artifacts，no distortion"
)

GENERIC_I2V = (
    "cinematic quality，smooth motion，"
    "stable character appearance，"
    "natural movement，professional lighting，"
    "8K resolution，no morphing"
)

# ============ 平台适配 ============

PLATFORM_PROMPT_WRAPPERS = {
    "jimeng": "{prompt}，超清画质",
    "doubao": "{prompt}，高清画质，电影感",
    "generic": "{prompt}",
}


def wrap_prompt(prompt: str, platform: str = "generic") -> str:
    """为不同平台包装提示词"""
    wrapper = PLATFORM_PROMPT_WRAPPERS.get(platform, PLATFORM_PROMPT_WRAPPERS["generic"])
    return wrapper.format(prompt=prompt)
