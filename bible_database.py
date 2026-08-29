# bible_database.py
# 圣经数据库接口层
# 说明：当前为示例数据，对接真实数据库时，
#       只需要修改本文件的查询方法，保持方法名和返回格式不变即可

class BibleDatabase:
    def __init__(self, db_path=None):
        # ===== 旧约书卷列表：(全名, 简称, 拼音首字母) =====
        self.old_testament = [
            ("创世记", "创", "cj"), ("出埃及记", "出", "chj"), ("利未记", "利", "lwj"),
            ("民数记", "民", "msj"), ("申命记", "申", "smmj"), ("约书亚记", "书", "ysyj"),
            ("士师记", "士", "ssj"), ("路得记", "得", "ldj"), ("撒母耳记上", "撒上", "smes"),
            ("撒母耳记下", "撒下", "smex"), ("列王纪上", "王上", "lwws"), ("列王纪下", "王下", "lwwx"),
            ("历代志上", "代上", "ldzs"), ("历代志下", "代下", "ldzx"), ("以斯拉记", "拉", "yzlj"),
            ("尼希米记", "尼", "nxmj"), ("以斯帖记", "斯", "ystj"), ("约伯记", "伯", "ybj"),
            ("诗篇", "诗", "sp"), ("箴言", "箴", "zy"), ("传道书", "传", "cds"),
            ("雅歌", "歌", "yg"), ("以赛亚书", "赛", "ysys"), ("耶利米书", "耶", "ylms"),
            ("耶利米哀歌", "哀", "ylmag"), ("以西结书", "结", "xyjs"), ("但以理书", "但", "dyls"),
            ("何西阿书", "何", "hxas"), ("约珥书", "珥", "yes"), ("阿摩司书", "摩", "amss"),
            ("俄巴底亚书", "俄", "ebdy"), ("约拿书", "拿", "yns"), ("弥迦书", "弥", "mjs"),
            ("那鸿书", "鸿", "nhs"), ("哈巴谷书", "哈", "hbgs"), ("西番雅书", "番", "xfys"),
            ("哈该书", "该", "hgs"), ("撒迦利亚书", "亚", "sjly"), ("玛拉基书", "玛", "mljs")
        ]

        # ===== 新约书卷列表 =====
        self.new_testament = [
            ("马太福音", "太", "mtfy"), ("马可福音", "可", "mkfy"), ("路加福音", "路", "lkfy"),
            ("约翰福音", "约", "yhfy"), ("使徒行传", "徒", "stxz"), ("罗马书", "罗", "lms"),
            ("哥林多前书", "林前", "lldqs"), ("哥林多后书", "林后", "lldhs"), ("加拉太书", "加", "jlts"),
            ("以弗所书", "弗", "yfs"), ("腓立比书", "腓", "flbs"), ("歌罗西书", "西", "glxs"),
            ("帖撒罗尼迦前书", "帖前", "tslnqs"), ("帖撒罗尼迦后书", "帖后", "tslnhs"),
            ("提摩太前书", "提前", "tmts"), ("提摩太后书", "提后", "tmth"),
            ("提多书", "多", "tds"), ("腓利门书", "门", "flms"), ("希伯来书", "来", "xbls"),
            ("雅各书", "雅", "ygs"), ("彼得前书", "彼前", "bdqs"), ("彼得后书", "彼后", "bdhs"),
            ("约翰一书", "约一", "yhys"), ("约翰二书", "约二", "yhes"), ("约翰三书", "约三", "yhss"),
            ("犹大书", "犹", "yds"), ("启示录", "启", "qsl")
        ]

        # 构建搜索索引（简拼、简称快速匹配）
        self._build_search_index()

        # ===== 各书卷总章节数（示例） =====
        self.chapter_counts = {
            "创世记": 50, "出埃及记": 40, "诗篇": 150, "箴言": 31,
            "马太福音": 28, "马可福音": 16, "路加福音": 24, "约翰福音": 21,
            "使徒行传": 28, "罗马书": 16, "希伯来书": 13, "启示录": 22
        }

    # ============== 搜索索引构建 ==============
    def _build_search_index(self):
        """构建简拼+简称的快速查找字典"""
        self.pinyin_map = {}
        all_books = self.old_testament + self.new_testament
        for book_name, short_name, pinyin in all_books:
            self.pinyin_map[pinyin] = book_name       # 完整简拼
            self.pinyin_map[pinyin[:2]] = book_name    # 首两字母简拼
            self.pinyin_map[short_name] = book_name    # 简称

    # ============== 书卷查询 ==============
    def get_books(self, category="all"):
        """
        获取书卷列表
        :param category: old(旧约)/new(新约)/all(全部)
        :return: [(全名, 简称), ...]
        """
        if category == "old":
            return [(name, short) for name, short, _ in self.old_testament]
        elif category == "new":
            return [(name, short) for name, short, _ in self.new_testament]
        return [(name, short) for name, short, _ in self.old_testament + self.new_testament]

    def search_books(self, query):
        """
        根据输入模糊搜索书卷
        :param query: 简拼/书名/简称
        :return: 匹配的书卷名列表
        """
        query = query.lower().strip()
        if not query:
            return []

        results = []
        all_books = self.old_testament + self.new_testament

        # 匹配简拼、全名、简称
        for book_name, short_name, pinyin in all_books:
            if query in pinyin or query in book_name or query in short_name:
                if book_name not in results:
                    results.append(book_name)
        return results

    # ============== 章节查询 ==============
    def get_chapter_count(self, book_name):
        """获取指定书卷的总章节数"""
        return self.chapter_counts.get(book_name, 10)

    def get_verse_count(self, book_name, chapter):
        """
        获取指定章的总节数
        【对接真实数据库时修改此处】
        """
        # 示例数据，实际从数据库读取
        demo_data = {
            ("创世记", 1): 31,
            ("约翰福音", 3): 36,
            ("诗篇", 23): 6
        }
        return demo_data.get((book_name, chapter), 30)

    def get_verse_text(self, book_name, chapter, verse):
        """
        获取单节经文内容
        【对接真实数据库时修改此处】
        :return: 经文文本字符串
        """
        # 示例占位文本，替换为真实经文
        return f"这是{book_name}第{chapter}章第{verse}节的经文内容。神爱世人，甚至将他的独生子赐给他们，叫一切信他的，不至灭亡，反得永生。"

    def get_verse_range(self, book_name, chapter, start_verse, end_verse=None):
        """
        获取指定范围的经文
        :param end_verse: 结束节，None表示到章末
        :return: [(节号, 经文内容), ...]
        """
        max_verse = self.get_verse_count(book_name, chapter)
        # 结束节超出范围或为空时，取到章末
        if end_verse is None or end_verse > max_verse:
            end_verse = max_verse

        return [
            (v, self.get_verse_text(book_name, chapter, v))
            for v in range(start_verse, end_verse + 1)
        ]

    # ============== 经文引用解析 ==============
    def parse_reference(self, text):
        """
        解析用户输入的经文引用
        支持格式：约 3:16 / 创 1 / 诗 23:1- / 约 3.16
        :return: (书卷名, 章节, 起始节, 结束节)
                 起始节为None表示整章；结束节为None表示到章末
        """
        text = text.strip()
        if not text:
            return None

        # 统一中文/英文分隔符
        text = text.replace("：", ":").replace("．", ".").replace("。", ".")
        parts = text.split()
        if not parts:
            return None

        # 第一步：匹配书卷
        books = self.search_books(parts[0])
        if not books:
            return None
        book_name = books[0]

        # 只有书卷名，默认第1章整章
        if len(parts) == 1:
            return (book_name, 1, None, None)

        # 第二步：解析章节部分
        chapter_part = parts[1]

        # 分离章号和节号
        if ":" in chapter_part:
            ch, ver = chapter_part.split(":", 1)
        elif "." in chapter_part:
            ch, ver = chapter_part.split(".", 1)
        else:
            ch, ver = chapter_part, None

        # 章号转数字，失败默认第1章
        try:
            chapter = int(ch)
        except ValueError:
            chapter = 1

        start_verse, end_verse = None, None

        # 第三步：解析节号范围
        if ver:
            if "-" in ver:
                # 范围格式：15-20 / 15- / -20
                s, e = ver.split("-", 1)
                start_verse = int(s) if s else 1
                end_verse = int(e) if e else None
            else:
                # 单节
                try:
                    start_verse = int(ver)
                    end_verse = start_verse
                except ValueError:
                    pass

        return (book_name, chapter, start_verse, end_verse)

    def close(self):
        """关闭数据库连接，预留接口"""
        pass
