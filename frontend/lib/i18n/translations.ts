// UI-chrome translations (navigation, top bar, login, common actions,
// settings). Deliberately scoped to the app's own interface text, not the
// content staff work with (document/poster titles, notes, etc. stay
// exactly as entered/parsed) - translating user data would risk silently
// altering official records.
export const en = {
  "nav.dashboard": "Dashboard",
  "nav.documents": "Documents",
  "nav.posters": "Poster Archive",
  "nav.search": "Search",
  "nav.ai": "AI Insights",
  "nav.users": "Users",
  "nav.settings": "Settings",

  "topbar.searchPlaceholder": "Search or jump to...",
  "topbar.profile": "Profile",
  "topbar.settings": "Settings",
  "topbar.signOut": "Sign out",
  "topbar.language": "Language",

  "login.title": "Office Automation Platform",
  "login.subtitle": "Sign in to continue",
  "login.signInHeading": "Sign in",
  "login.signInDescription": "Enter your office credentials.",
  "login.username": "Username",
  "login.password": "Password",
  "login.signIn": "Sign in",
  "login.mfaHeading": "Two-factor verification",
  "login.mfaDescription": "Enter the 6-digit code from your authenticator app, or a recovery code.",
  "login.authCode": "Authentication code",
  "login.verify": "Verify",
  "login.backToSignIn": "Back to sign in",

  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.upload": "Upload",
  "common.exportCsv": "Export CSV",
  "common.loading": "Loading...",

  "settings.language": "Language",
  "settings.languageDescription": "Choose the interface language. This only changes the app's own menus and labels - document and poster content is never translated.",
} as const;

export type TranslationKey = keyof typeof en;

// 廣東話 / 繁體中文 - Hong Kong Traditional Chinese, the office's primary
// working language (matches config/rules/*.yaml's existing Traditional
// Chinese district/estate names).
export const zhHK: Record<TranslationKey, string> = {
  "nav.dashboard": "儀表板",
  "nav.documents": "文件",
  "nav.posters": "海報存檔",
  "nav.search": "搜尋",
  "nav.ai": "AI 洞察",
  "nav.users": "使用者",
  "nav.settings": "設定",

  "topbar.searchPlaceholder": "搜尋或跳轉至...",
  "topbar.profile": "個人資料",
  "topbar.settings": "設定",
  "topbar.signOut": "登出",
  "topbar.language": "語言",

  "login.title": "辦公室自動化平台",
  "login.subtitle": "請登入以繼續",
  "login.signInHeading": "登入",
  "login.signInDescription": "請輸入您的辦公室帳號。",
  "login.username": "使用者名稱",
  "login.password": "密碼",
  "login.signIn": "登入",
  "login.mfaHeading": "雙重驗證",
  "login.mfaDescription": "請輸入驗證器應用程式的 6 位數代碼，或使用備用代碼。",
  "login.authCode": "驗證碼",
  "login.verify": "驗證",
  "login.backToSignIn": "返回登入",

  "common.save": "儲存",
  "common.cancel": "取消",
  "common.delete": "刪除",
  "common.edit": "編輯",
  "common.upload": "上傳",
  "common.exportCsv": "匯出 CSV",
  "common.loading": "載入中...",

  "settings.language": "語言",
  "settings.languageDescription": "選擇介面語言。此設定只影響應用程式本身的選單及標籤，文件及海報內容不會被翻譯。",
};

// 普通话 / 简体中文 - Mandarin Simplified Chinese.
export const zhCN: Record<TranslationKey, string> = {
  "nav.dashboard": "仪表板",
  "nav.documents": "文件",
  "nav.posters": "海报存档",
  "nav.search": "搜索",
  "nav.ai": "AI 洞察",
  "nav.users": "用户",
  "nav.settings": "设置",

  "topbar.searchPlaceholder": "搜索或跳转至...",
  "topbar.profile": "个人资料",
  "topbar.settings": "设置",
  "topbar.signOut": "登出",
  "topbar.language": "语言",

  "login.title": "办公室自动化平台",
  "login.subtitle": "请登录以继续",
  "login.signInHeading": "登录",
  "login.signInDescription": "请输入您的办公室账号。",
  "login.username": "用户名",
  "login.password": "密码",
  "login.signIn": "登录",
  "login.mfaHeading": "双重验证",
  "login.mfaDescription": "请输入验证器应用程序的 6 位数代码，或使用备用代码。",
  "login.authCode": "验证码",
  "login.verify": "验证",
  "login.backToSignIn": "返回登录",

  "common.save": "保存",
  "common.cancel": "取消",
  "common.delete": "删除",
  "common.edit": "编辑",
  "common.upload": "上传",
  "common.exportCsv": "导出 CSV",
  "common.loading": "加载中...",

  "settings.language": "语言",
  "settings.languageDescription": "选择界面语言。此设置仅影响应用程序本身的菜单和标签，文件及海报内容不会被翻译。",
};

export const dictionaries = { en, "zh-HK": zhHK, "zh-CN": zhCN } as const;
export type Locale = keyof typeof dictionaries;

export const localeLabels: Record<Locale, string> = {
  en: "English",
  "zh-HK": "廣東話（繁體中文）",
  "zh-CN": "普通话（简体中文）",
};
