"""单一版本号来源（与 file_version_info.txt、Bible Pro.iss 对齐）。"""

APP_NAME = "Bible Pro"
APP_VERSION = "3.0.0"

# 自动更新：版本信息读 GitHub；安装包经 gh-proxy 加速下载
GITHUB_OWNER = "XiaoDong1213"
GITHUB_REPO = "bible_projection"
GITHUB_RELEASES_LATEST_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

RELEASES_LATEST_API = GITHUB_RELEASES_LATEST_API
RELEASES_PAGE = GITHUB_RELEASES_PAGE
