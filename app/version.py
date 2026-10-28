"""单一版本号来源（与 file_version_info.txt、Bible Pro.iss 对齐）。"""

APP_NAME = "Bible Pro"
APP_VERSION = "2.2.0"

# 自动更新：版本信息读 GitHub；安装包经快节点下载
GITHUB_OWNER = "XiaoDong1213"
GITHUB_REPO = "bible_projection"
GITHUB_RELEASES_LATEST_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Gitea 镜像（发版同步用；检查更新不再依赖）
GITEA_BASE = "https://gitea.cccccjd.cn"
GITEA_OWNER = "SXD20041213"
GITEA_REPO = "bible_projection"
GITEA_RELEASES_LATEST_API = (
    f"{GITEA_BASE}/api/v1/repos/{GITEA_OWNER}/{GITEA_REPO}/releases/latest"
)
GITEA_RELEASES_PAGE = f"{GITEA_BASE}/{GITEA_OWNER}/{GITEA_REPO}/releases"

RELEASES_LATEST_API = GITHUB_RELEASES_LATEST_API
RELEASES_PAGE = GITHUB_RELEASES_PAGE
