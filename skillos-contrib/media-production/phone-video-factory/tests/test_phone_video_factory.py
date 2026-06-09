import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestPlatformCapabilities:
    def test_all_platforms_have_required_fields(self):
        from references.platform_capabilities import PLATFORM_CAPABILITIES

        required = (
            "name",
            "package",
            "free_quota",
            "video_format",
            "verified",
        )
        for platform, caps in PLATFORM_CAPABILITIES.items():
            for field in required:
                assert field in caps, f"{platform} missing {field}"

    def test_verified_platforms_match_skill_md(self):
        from references.platform_capabilities import PLATFORM_CAPABILITIES

        assert PLATFORM_CAPABILITIES["jimeng"]["verified"] is True
        assert PLATFORM_CAPABILITIES["doubao"]["verified"] is True
        assert PLATFORM_CAPABILITIES["qianwen_app"]["verified"] is False
        assert PLATFORM_CAPABILITIES["jianying"]["verified"] is False

    def test_jimeng_has_compose_fields(self):
        from references.platform_capabilities import PLATFORM_CAPABILITIES

        jimeng = PLATFORM_CAPABILITIES["jimeng"]
        assert jimeng["ui_type"] == "Jetpack Compose (NavigationBar + Button/FAB)"
        assert "compose_tab_bar" in jimeng
        assert "compose_buttons" in jimeng
        assert "600-835px" in jimeng["notes"]

    def test_doubao_has_codec_and_auto_save_fields(self):
        from references.platform_capabilities import PLATFORM_CAPABILITIES

        doubao = PLATFORM_CAPABILITIES["doubao"]
        assert "auto_save" in doubao
        assert "codec_fix" in doubao
        assert "HEVC" in doubao["video_format"]

    def test_zflip3_device_info(self):
        from references.platform_capabilities import ZFLIP3_DEVICE

        assert ZFLIP3_DEVICE["id"] == "R3CR80FKA0V"
        assert ZFLIP3_DEVICE["resolution"] == "1080x2640"


class TestJimengPlatform:
    def test_tab_bar_coordinates(self):
        from platforms.jimeng import TAB_BAR, TAB_BAR_BOUNDS

        assert TAB_BAR["首页"] == (180, 2429)
        assert TAB_BAR["创作"] == (540, 2429)
        assert TAB_BAR["我的"] == (900, 2429)
        assert TAB_BAR_BOUNDS == (0, 2219, 1080, 2640)

    def test_tab_bar_coords_within_tab_bar_bounds(self):
        from platforms.jimeng import TAB_BAR, TAB_BAR_BOUNDS

        x1, y1, x2, y2 = TAB_BAR_BOUNDS
        for name, (x, y) in TAB_BAR.items():
            assert x1 <= x <= x2, f"{name} x={x} out of bounds [{x1},{x2}]"
            assert y1 <= y <= y2, f"{name} y={y} out of bounds [{y1},{y2}]"

    def test_build_jimeng_i2v_task_with_ref(self):
        from platforms.jimeng import build_jimeng_task

        task = build_jimeng_task(mode="i2v", prompt="测试提示词", has_ref_image=True)
        assert "即梦" in task
        assert "图生视频" in task
        assert "测试提示词" in task
        assert "上传图片" in task

    def test_build_jimeng_t2v_task(self):
        from platforms.jimeng import build_jimeng_task

        task = build_jimeng_task(mode="t2v", prompt="科幻场景", has_ref_image=False)
        assert "即梦" in task
        assert "文生视频" in task
        assert "科幻场景" in task

    def test_jimeng_video_storage_paths(self):
        from platforms.jimeng import JIMENG_VIDEO_PATH, JIMENG_VIDEO_PATTERN

        assert JIMENG_VIDEO_PATH == "/sdcard/Movies"
        assert JIMENG_VIDEO_PATTERN == "dreamina_*.mp4"

    def test_get_jimeng_pull_command(self):
        from platforms.jimeng import get_jimeng_pull_command

        cmd = get_jimeng_pull_command("/tmp/output")
        assert "adb pull" in cmd
        assert "/sdcard/Movies/dreamina_*.mp4" in cmd
        assert "/tmp/output/" in cmd

    def test_get_jimeng_cleanup_command(self):
        from platforms.jimeng import get_jimeng_cleanup_command

        cmd = get_jimeng_cleanup_command()
        assert "adb shell rm" in cmd
        assert "/sdcard/Movies/dreamina_*.mp4" in cmd


class TestDoubaoPlatform:
    def test_doubao_auto_save_path(self):
        from platforms.doubao import DOUBAO_AUTO_SAVE

        assert "com.larus.nova" in DOUBAO_AUTO_SAVE
        assert "nova_video" in DOUBAO_AUTO_SAVE

    def test_doubao_ui_hints_marked_unverified(self):
        from platforms.doubao import DOUBAO_UI_HINTS_UNVERIFIED

        assert "ai_tab" in DOUBAO_UI_HINTS_UNVERIFIED
        assert len(DOUBAO_UI_HINTS_UNVERIFIED) == 5

    def test_build_doubao_i2v_task(self):
        from platforms.doubao import build_doubao_task

        task = build_doubao_task(mode="i2v", prompt="AI角色特写", has_ref_image=True)
        assert "豆包" in task
        assert "AI创作" in task
        assert "AI角色特写" in task
        assert "上传图片" in task

    def test_build_doubao_t2v_task(self):
        from platforms.doubao import build_doubao_task

        task = build_doubao_task(mode="t2v", prompt="自然风景", has_ref_image=False)
        assert "豆包" in task
        assert "AI视频" in task
        assert "自然风景" in task


class TestAdbMedia:
    def test_phone_video_paths_include_jimeng_and_doubao(self):
        from utils.adb_media import PHONE_VIDEO_PATHS

        assert any("dreamina" in p for p in PHONE_VIDEO_PATHS)
        assert any("nova_video" in p for p in PHONE_VIDEO_PATHS)

    def test_default_output_dir_exists(self):
        from utils.adb_media import DEFAULT_OUTPUT_DIR

        assert DEFAULT_OUTPUT_DIR.exists() or DEFAULT_OUTPUT_DIR.name == "phone_gen"

    def test_push_ref_fails_on_missing_file(self):
        from utils.adb_media import push_reference_image

        result = push_reference_image("fake_device", "/nonexistent/image.jpg")
        assert result is False


class TestAthenaPrompts:
    def test_all_templates_non_empty(self):
        from templates.athena_prompts import (
            ATHENA_I2V_BASE,
            ATHENA_I2V_TALKING,
            ATHENA_T2V_CLOSEUP,
            ATHENA_T2V_FULLBODY,
            ATHENA_T2V_PORTRAIT,
            GENERIC_I2V,
            GENERIC_T2V,
        )

        templates = [
            ATHENA_T2V_PORTRAIT,
            ATHENA_T2V_CLOSEUP,
            ATHENA_T2V_FULLBODY,
            ATHENA_I2V_BASE,
            ATHENA_I2V_TALKING,
            GENERIC_T2V,
            GENERIC_I2V,
        ]
        for t in templates:
            assert len(t) > 30, f"Template too short: {t[:30]}..."

    def test_wrap_prompt_for_different_platforms(self):
        from templates.athena_prompts import wrap_prompt

        jimeng_prompt = wrap_prompt("测试", "jimeng")
        assert "超清画质" in jimeng_prompt
        assert "测试" in jimeng_prompt

        doubao_prompt = wrap_prompt("测试", "doubao")
        assert "电影感" in doubao_prompt

        generic_prompt = wrap_prompt("测试", "unknown_platform")
        assert generic_prompt == "测试"


class TestInitImports:
    def test_platforms_init_exports(self):
        from platforms import (
            DOUBAO_AUTO_SAVE,
            TAB_BAR,
            build_doubao_task,
            build_jimeng_task,
            switch_tab,
            tap_compose,
        )

        assert TAB_BAR["首页"] == (180, 2429)
        assert tap_compose is not None
        assert switch_tab is not None
        assert "com.larus.nova" in DOUBAO_AUTO_SAVE
        assert build_jimeng_task is not None
        assert build_doubao_task is not None

    def test_utils_init_exports(self):
        from utils import (
            cleanup_phone_videos,
            pull_latest_videos,
            push_reference_image,
        )

        assert pull_latest_videos is not None
        assert push_reference_image is not None
        assert cleanup_phone_videos is not None

    def test_templates_init_exports(self):
        from templates import (
            ATHENA_T2V_PORTRAIT,
            GENERIC_I2V,
            wrap_prompt,
        )

        assert len(ATHENA_T2V_PORTRAIT) > 50
        assert len(GENERIC_I2V) > 20
        assert wrap_prompt is not None
