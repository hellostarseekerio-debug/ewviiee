/**
 * The 11 cities of the Greater Bay Area.
 * lon/lat are mapped onto the scene plane; gdp in US$ billions (indicative, for scale).
 * `hub: true` marks the three gateway cities that receive the cinematic camera treatment.
 */
export const CITIES = [
  { id: 'hk',  en: 'Hong Kong', zh: '香港', cn: '香港', lon: 114.17, lat: 22.30, gdp: 382, hub: true,
    techEn: 'Global finance gateway · IPO capital of Asia', techZh: '國際金融門戶 · 亞洲新股集資之都', techCn: '国际金融门户 · 亚洲新股融资之都' },
  { id: 'sz',  en: 'Shenzhen', zh: '深圳', cn: '深圳', lon: 114.06, lat: 22.55, gdp: 482, hub: true,
    techEn: 'Hardware, AI & advanced R&D engine', techZh: '硬件、人工智能及尖端研發引擎', techCn: '硬件、人工智能及尖端研发引擎' },
  { id: 'gz',  en: 'Guangzhou', zh: '廣州', cn: '广州', lon: 113.26, lat: 23.13, gdp: 423, hub: true,
    techEn: 'Trade, biotech & smart manufacturing', techZh: '商貿、生物科技及智能製造', techCn: '商贸、生物科技及智能制造' },
  { id: 'mo',  en: 'Macau', zh: '澳門', cn: '澳门', lon: 113.55, lat: 22.19, gdp: 47,
    techEn: 'Leisure capital · Lusophone gateway', techZh: '休閒之都 · 葡語市場門戶', techCn: '休闲之都 · 葡语市场门户' },
  { id: 'zh',  en: 'Zhuhai', zh: '珠海', cn: '珠海', lon: 113.58, lat: 22.27, gdp: 57,
    techEn: 'Aerospace & integrated circuits', techZh: '航空航天及集成電路', techCn: '航空航天及集成电路' },
  { id: 'fs',  en: 'Foshan', zh: '佛山', cn: '佛山', lon: 113.12, lat: 23.02, gdp: 186,
    techEn: 'Robotics & home-tech manufacturing', techZh: '機械人及家電科技製造', techCn: '机器人及家电科技制造' },
  { id: 'dg',  en: 'Dongguan', zh: '東莞', cn: '东莞', lon: 113.75, lat: 23.02, gdp: 157,
    techEn: 'Electronics & smart devices', techZh: '電子產品及智能設備', techCn: '电子产品及智能设备' },
  { id: 'hui', en: 'Huizhou', zh: '惠州', cn: '惠州', lon: 114.41, lat: 23.11, gdp: 77,
    techEn: 'New energy & petrochemicals', techZh: '新能源及石化產業', techCn: '新能源及石油化工' },
  { id: 'zs',  en: 'Zhongshan', zh: '中山', cn: '中山', lon: 113.39, lat: 22.52, gdp: 51,
    techEn: 'Optoelectronics & health tech', techZh: '光電及健康科技', techCn: '光电及健康科技' },
  { id: 'jm',  en: 'Jiangmen', zh: '江門', cn: '江门', lon: 113.08, lat: 22.58, gdp: 56,
    techEn: 'New materials & equipment', techZh: '新材料及裝備製造', techCn: '新材料及装备制造' },
  { id: 'zq',  en: 'Zhaoqing', zh: '肇慶', cn: '肇庆', lon: 112.47, lat: 23.05, gdp: 39,
    techEn: 'Auto parts & green industry', techZh: '汽車零部件及綠色產業', techCn: '汽车零部件及绿色产业' },
]

/** City display name / tech line for the active locale. */
export function cityLabel(city, lang) {
  return lang === 'en' ? city.en : lang === 'zh' ? city.zh : city.cn
}

export function cityTech(city, lang) {
  return lang === 'en' ? city.techEn : lang === 'zh' ? city.techZh : city.techCn
}

const CENTER = { lon: 113.45, lat: 22.68 }
const SCALE = { x: 5.2, y: 6.4 }

/** Map geographic coordinates to scene-space [x, y, z]. */
export function cityPosition(city) {
  return [
    (city.lon - CENTER.lon) * SCALE.x,
    (city.lat - CENTER.lat) * SCALE.y,
    0,
  ]
}

export const HUB_IDS = CITIES.filter((c) => c.hub).map((c) => c.id)
