//! Slate Browser — a Rust browser with a full-height site rail.
//!
//! The shell uses a graphite palette, a single active surface, compact
//! controls and subtle 180 ms ease-out tab transitions.
//!
//! Every surface is drawn by Makepad in Rust. Pages are rendered by the
//! platform WebView through Makepad's native layer, so Android Chromium does
//! the page work while the chrome stays 100% Rust.

pub use makepad_widgets;
use makepad_widgets::makepad_platform::storage::{
    StorageRequestId, StorageResponse, StorageResult,
};
use makepad_widgets::*;
use std::collections::HashSet;

app_main!(App);

const SITES: [(&str, &str); 6] = [
    ("Wikipedia", "https://en.wikipedia.org"),
    ("Hacker News", "https://news.ycombinator.com"),
    ("GitHub", "https://github.com"),
    ("DuckDuckGo", "https://duckduckgo.com"),
    ("YouTube", "https://www.youtube.com"),
    ("Internet Archive", "https://archive.org"),
];

const SEARCH_SOURCES: [(&str, &str); 2] = [
    ("DuckDuckGo", "https://html.duckduckgo.com/html/?q="),
    ("Bing", "https://www.bing.com/search?q="),
];
const SOURCE_PRESETS: [&str; 3] = ["Both", "DuckDuckGo", "Bing"];
const SEARCH_RESULTS: usize = 8;
const SEARCH_USER_AGENT: &str =
    "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/131 Mobile Safari/537.36";

#[derive(Clone, Debug)]
struct SearchResult {
    title: String,
    url: String,
    source: usize,
}

const THEMES: [&str; 3] = ["Moon dark", "Paper light", "Skeleton"];
const ACCENTS: [&str; 3] = ["Ice", "Copper", "Moss"];
const RAIL_WIDTHS: [f64; 3] = [64.0, 72.0, 84.0];

#[derive(Clone, Copy, Debug, PartialEq)]
enum Surface {
    Start,
    Page,
    Settings,
    History,
    Sites,
    Search,
}

impl Default for Surface {
    fn default() -> Self {
        Self::Start
    }
}

#[derive(Clone, Debug)]
struct Site {
    label: String,
    url: String,
    custom: bool,
}

impl Site {
    fn default_site(index: usize) -> Self {
        Self {
            label: SITES[index].0.to_string(),
            url: SITES[index].1.to_string(),
            custom: false,
        }
    }
}

#[derive(Clone, Debug)]
struct Settings {
    theme: u8,
    accent: u8,
    rail: u8,
    labels: bool,
    engine: u8,
    reduced_motion: bool,
    tabs: [String; 3],
    active: usize,
    history: Vec<String>,
    sites: Vec<Site>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            theme: 0,
            accent: 0,
            rail: 0,
            labels: false,
            engine: 0,
            reduced_motion: false,
            tabs: [String::new(), String::new(), String::new()],
            active: 0,
            history: Vec::new(),
            sites: (0..SITES.len()).map(Site::default_site).collect(),
        }
    }
}

impl Settings {
    fn encode(&self) -> String {
        let mut out = String::from("slate-v2\n");
        out.push_str(&format!("theme={}\n", self.theme));
        out.push_str(&format!("accent={}\n", self.accent));
        out.push_str(&format!("rail={}\n", self.rail));
        out.push_str(&format!("labels={}\n", u8::from(self.labels)));
        out.push_str(&format!("engine={}\n", self.engine));
        out.push_str(&format!("reduced={}\n", u8::from(self.reduced_motion)));
        out.push_str(&format!("active={}\n", self.active));
        for (i, tab) in self.tabs.iter().enumerate() {
            if !tab.is_empty() {
                out.push_str(&format!("tab={i}|{tab}\n"));
            }
        }
        for url in self.history.iter().take(24) {
            out.push_str(&format!("hist={url}\n"));
        }
        for (i, site) in self.sites.iter().enumerate() {
            if site.custom {
                out.push_str(&format!("site={i}|{}|{}\n", site.label, site.url));
            }
        }
        out
    }

    fn decode(text: &str) -> Option<Self> {
        let mut lines = text.lines();
        let version = lines.next()?;
        if version != "slate-v1" && version != "slate-v2" {
            return None;
        }
        let mut s = Self::default();
        for line in lines {
            if let Some(value) = line.strip_prefix("theme=") {
                s.theme = value.parse().unwrap_or(0).min(2);
            } else if let Some(value) = line.strip_prefix("accent=") {
                s.accent = value.parse().unwrap_or(0).min(2);
            } else if let Some(value) = line.strip_prefix("rail=") {
                s.rail = value.parse().unwrap_or(0).min(2);
            } else if let Some(value) = line.strip_prefix("labels=") {
                s.labels = value == "1";
            } else if let Some(value) = line.strip_prefix("engine=") {
                s.engine = value.parse().unwrap_or(0).min(2);
            } else if let Some(value) = line.strip_prefix("reduced=") {
                s.reduced_motion = value == "1";
            } else if let Some(value) = line.strip_prefix("active=") {
                s.active = value.parse().unwrap_or(0).min(2);
            } else if let Some(value) = line.strip_prefix("tab=") {
                let mut parts = value.splitn(2, '|');
                let index: usize = parts.next()?.parse().ok()?;
                if let (Some(url), Some(slot)) = (parts.next(), s.tabs.get_mut(index)) {
                    *slot = url.to_string();
                }
            } else if let Some(url) = line.strip_prefix("hist=") {
                s.history.push(url.to_string());
            } else if let Some(value) = line.strip_prefix("site=") {
                let mut parts = value.splitn(3, '|');
                let index: usize = parts.next()?.parse().ok()?;
                let label = parts.next()?.to_string();
                let url = parts.next()?.to_string();
                if let Some(slot) = s.sites.get_mut(index) {
                    *slot = Site {
                        label,
                        url,
                        custom: true,
                    };
                }
            }
        }
        Some(s)
    }
}

fn host_of(url: &str) -> String {
    let after_scheme = url.split("://").nth(1).unwrap_or(url);
    let host = after_scheme.split('/').next().unwrap_or(after_scheme);
    host.split('@').last().unwrap_or(host).to_string()
}

fn short_host(url: &str, limit: usize) -> String {
    let host = host_of(url);
    let trimmed = host.trim_start_matches("www.");
    let parts: Vec<&str> = trimmed.split('.').filter(|p| !p.is_empty()).collect();
    let picked = if parts.len() > 1 && parts[0].len() <= 3 && parts[0] != "news" {
        parts[1]
    } else {
        parts.first().copied().unwrap_or("site")
    };
    let mut out: String = picked.chars().take(limit).collect();
    if let Some(first) = out.get_mut(0..1) {
        first.make_ascii_uppercase();
    }
    if out.is_empty() {
        out.push_str("Site");
    }
    out
}

fn site_label_from_url(url: &str) -> String {
    short_host(url, 12)
}

fn tab_label(url: &str, index: usize) -> String {
    if url.is_empty() {
        return format!("{}", index + 1);
    }
    short_host(url, 7)
}

fn percent_encode(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    for byte in input.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char)
            }
            _ => out.push_str(&format!("%{byte:02X}")),
        }
    }
    out
}

fn percent_decode(input: &str) -> String {
    let bytes = input.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            let hex = &input[i + 1..i + 3];
            if let Ok(value) = u8::from_str_radix(hex, 16) {
                out.push(value);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn html_unescape(input: &str) -> String {
    let mut out = input.to_string();
    for (from, to) in [
        ("&#39;", "'"),
        ("&#x27;", "'"),
        ("&quot;", "\""),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&nbsp;", " "),
        ("&amp;", "&"),
    ] {
        out = out.replace(from, to);
    }
    out
}

fn strip_tags(input: &str) -> String {
    let mut out = String::new();
    let mut inside = false;
    for ch in input.chars() {
        if ch == '<' {
            inside = true;
        } else if ch == '>' {
            inside = false;
        } else if !inside {
            out.push(ch);
        }
    }
    html_unescape(&out).split_whitespace().collect::<Vec<_>>().join(" ")
}

fn attr(tag: &str, name: &str) -> Option<String> {
    let needle = format!("{name}=\"");
    let start = tag.find(&needle)? + needle.len();
    let end = tag[start..].find('"')? + start;
    Some(html_unescape(&tag[start..end]))
}

fn result_url(href: &str) -> String {
    let href = html_unescape(href);
    if let Some(pos) = href.find("uddg=") {
        let value = href[pos + 5..].split('&').next().unwrap_or("");
        let decoded = percent_decode(value);
        if decoded.starts_with("http://") || decoded.starts_with("https://") {
            return decoded;
        }
    }
    if href.starts_with("//") {
        return format!("https:{href}");
    }
    if href.starts_with("http://") || href.starts_with("https://") {
        return href;
    }
    String::new()
}

fn parse_ddg_results(html: &str) -> Vec<SearchResult> {
    let mut out = Vec::new();
    let mut rest = html;
    while let Some(pos) = rest.find("result__a") {
        let Some(open) = rest[..pos].rfind("<a ").or_else(|| rest[..pos].rfind("<a>")) else {
            rest = &rest[pos + 9..];
            continue;
        };
        let Some(gt) = rest[open..].find('>').map(|i| open + i) else {
            break;
        };
        let href = attr(&rest[open..gt], "href").unwrap_or_default();
        let body_start = gt + 1;
        let Some(close) = rest[body_start..].find("</a>").map(|i| body_start + i) else {
            break;
        };
        let title = strip_tags(&rest[body_start..close]);
        let url = result_url(&href);
        if !title.is_empty() && !url.is_empty() {
            out.push(SearchResult { title, url, source: 0 });
        }
        rest = &rest[close + 4..];
    }
    out
}

fn parse_bing_results(html: &str) -> Vec<SearchResult> {
    let mut out = Vec::new();
    let mut rest = html;
    while let Some(pos) = rest.find("class=\"b_algo\"") {
        let section = &rest[pos..];
        let Some(open) = section.find("<a ") else {
            break;
        };
        let Some(gt) = section[open..].find('>').map(|i| open + i) else {
            break;
        };
        let href = attr(&section[open..gt], "href").unwrap_or_default();
        let body_start = gt + 1;
        let Some(close) = section[body_start..].find("</a>").map(|i| body_start + i) else {
            break;
        };
        let title = strip_tags(&section[body_start..close]);
        let url = result_url(&href);
        if !title.is_empty() && !url.is_empty() {
            out.push(SearchResult { title, url, source: 1 });
        }
        rest = &rest[pos + close + 4..];
    }
    out
}

fn parse_search_results(source: usize, html: &str) -> Vec<SearchResult> {
    if source == 0 {
        parse_ddg_results(html)
    } else {
        parse_bing_results(html)
    }
}

fn merge_search_results(groups: &[Vec<SearchResult>]) -> Vec<SearchResult> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();
    let longest = groups.iter().map(Vec::len).max().unwrap_or(0);
    for rank in 0..longest {
        for group in groups {
            let Some(result) = group.get(rank) else {
                continue;
            };
            let key = result
                .url
                .split('?')
                .next()
                .unwrap_or(&result.url)
                .trim_end_matches('/')
                .to_string();
            if seen.insert(key) {
                out.push(result.clone());
                if out.len() == SEARCH_RESULTS {
                    return out;
                }
            }
        }
    }
    out
}

fn search_source_urls(query: &str, preset: u8) -> Vec<(usize, String)> {
    let encoded = percent_encode(query);
    let indices: &[usize] = match preset {
        1 => &[0],
        2 => &[1],
        _ => &[0, 1],
    };
    indices
        .iter()
        .map(|&i| (i, format!("{}{}", SEARCH_SOURCES[i].1, encoded)))
        .collect()
}

script_mod! {
    use mod.prelude.widgets.*
    use mod.widgets.*

    load_all_resources() do #(App::script_component(vm)){
        ui: Root{
            main_window := Window{
                window.title: "Slate Browser"
                window.inner_size: vec2(1080, 1920)
                pass +: {clear_color: theme.color_bg_app}
                body +: {
                    keyboard_resize: true
                    padding: Inset{top: mod.widgets.SAFE_INSET_PAD_TOP right: mod.widgets.SAFE_INSET_PAD_RIGHT bottom: mod.widgets.SAFE_INSET_PAD_BOTTOM left: mod.widgets.SAFE_INSET_PAD_LEFT}
                    margin: 0
                    spacing: 0
                    flow: Right
                    show_bg: true
                    draw_bg.color: theme.color_bg_app

                    shell := View{
                        width: Fill
                        height: Fill
                        flow: Down
                        spacing: 0
                        show_bg: true
                        draw_bg.color: theme.color_bg_app

                        header := View{
                            width: Fill
                            height: 88
                            flow: Down
                            spacing: 0
                            show_bg: true
                            draw_bg.color: theme.color_bg_container

                            tab_strip := View{
                                width: Fill
                                height: 34
                                flow: Right
                                spacing: 4
                                padding: Inset{left: 12 right: 12 top: 4 bottom: 0}

                                tab1_slot := View{
                                    width: 44 height: 30
                                    flow: Down spacing: 0
                                    tab1 := ButtonFlatter{
                                        width: Fill height: 28
                                        margin: 0 padding: 0
                                        text: "1"
                                        draw_text +: {
                                            color: theme.color_text_meta
                                            text_style: theme.font_bold{font_size: 11}
                                        }
                                    }
                                    tab1_mark := View{
                                        width: Fill height: 2
                                        show_bg: true
                                        draw_bg.color: theme.color_focus
                                        animator: Animator{
                                            active: {
                                                default: @off
                                                off: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 0.0}}
                                                on: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 2.0}}
                                            }
                                        }
                                    }
                                }

                                tab2_slot := View{
                                    width: 44 height: 30
                                    flow: Down spacing: 0
                                    tab2 := ButtonFlatter{
                                        width: Fill height: 28
                                        margin: 0 padding: 0
                                        text: "2"
                                        draw_text +: {
                                            color: theme.color_text_meta
                                            text_style: theme.font_bold{font_size: 11}
                                        }
                                    }
                                    tab2_mark := View{
                                        width: Fill height: 2
                                        show_bg: true
                                        draw_bg.color: theme.color_focus
                                        animator: Animator{
                                            active: {
                                                default: @off
                                                off: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 0.0}}
                                                on: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 2.0}}
                                            }
                                        }
                                    }
                                }

                                tab3_slot := View{
                                    width: 44 height: 30
                                    flow: Down spacing: 0
                                    tab3 := ButtonFlatter{
                                        width: Fill height: 28
                                        margin: 0 padding: 0
                                        text: "3"
                                        draw_text +: {
                                            color: theme.color_text_meta
                                            text_style: theme.font_bold{font_size: 11}
                                        }
                                    }
                                    tab3_mark := View{
                                        width: Fill height: 2
                                        show_bg: true
                                        draw_bg.color: theme.color_focus
                                        animator: Animator{
                                            active: {
                                                default: @off
                                                off: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 0.0}}
                                                on: AnimatorState{from: {all: Play.Forward{duration: 0.18}} ease: Ease.OutCubic apply: {walk.height: 2.0}}
                                            }
                                        }
                                    }
                                }

                                tab_gap := View{width: Fill height: Fill}
                                header_history := ButtonFlatterIcon{
                                    width: 28 height: 28
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/history.svg")
                                    draw_icon.color: theme.color_text_meta
                                    icon_walk: Walk{width: 16 height: Fit}
                                }
                            }

                            toolbar := View{
                                width: Fill
                                height: 54
                                flow: Right
                                spacing: 4
                                padding: Inset{left: 12 right: 12 top: 4 bottom: 8}
                                show_bg: true
                                draw_bg.color: theme.color_bg_container

                                back := ButtonFlatterIcon{
                                    width: 40 height: 40
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/back.svg")
                                    draw_icon.color: theme.color_text
                                    icon_walk: Walk{width: 18 height: Fit}
                                }
                                forward := ButtonFlatterIcon{
                                    width: 40 height: 40
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/forward.svg")
                                    draw_icon.color: theme.color_text
                                    icon_walk: Walk{width: 18 height: Fit}
                                }
                                search_go := ButtonFlatterIcon{
                                    width: 36 height: 40
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/search.svg")
                                    draw_icon.color: theme.color_text_meta
                                    icon_walk: Walk{width: 16 height: Fit}
                                }
                                omnibox := TextInput{
                                    width: Fill height: 40
                                    margin: Inset{left: 4 right: 4 top: 0 bottom: 0}
                                    empty_text: "Search or address"
                                    draw_bg +: {
                                        color: theme.color_inset
                                        color_focus: theme.color_inset
                                        border_size: 0
                                        border_radius: 8
                                    }
                                    draw_text +: {
                                        color: theme.color_text
                                        color_empty: theme.color_text_meta
                                        text_style: theme.font_regular{font_size: 13}
                                    }
                                }
                                reload := ButtonFlatterIcon{
                                    width: 40 height: 40
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/reload.svg")
                                    draw_icon.color: theme.color_text
                                    icon_walk: Walk{width: 18 height: Fit}
                                }
                                home := ButtonFlatterIcon{
                                    width: 40 height: 40
                                    margin: 0
                                    draw_icon.svg: crate_resource("self:resources/icons/home.svg")
                                    draw_icon.color: theme.color_focus
                                    icon_walk: Walk{width: 18 height: Fit}
                                }
                            }

                            load_bar := View{
                                visible: false
                                width: Fill height: 2
                                show_bg: true
                                draw_bg.color: theme.color_focus
                            }
                        }

                        stage := View{
                            width: Fill
                            height: Fill
                            flow: Overlay
                            clip_x: true
                            clip_y: true

                            page := WebView{
                                width: Fill
                                height: Fill
                                url: "about:blank"
                            }

                            start := View{
                                width: Fill height: Fill
                                flow: Down
                                spacing: 0
                                padding: Inset{left: 32 right: 32 top: 88 bottom: 24}
                                align: Align{x: 0.5 y: 0.0}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app

                                brand := Label{
                                    width: Fill height: 32
                                    text: "SLATE"
                                    align: Align{x: 0.5 y: 0.5}
                                    draw_text +: {
                                        color: theme.color_text
                                        text_style: theme.font_bold{font_size: 20}
                                    }
                                }
                                tagline := Label{
                                    width: Fill height: 24
                                    text: "A quiet place to go somewhere"
                                    align: Align{x: 0.5 y: 0.5}
                                    draw_text +: {
                                        color: theme.color_text_meta
                                        text_style: theme.font_regular{font_size: 11}
                                    }
                                }
                                start_search := TextInput{
                                    width: Fill height: 48
                                    margin: Inset{top: 32 left: 0 right: 0 bottom: 0}
                                    empty_text: "Search or type an address"
                                    draw_bg +: {
                                        color: theme.color_inset
                                        color_focus: theme.color_inset
                                        border_size: 0
                                        border_radius: 8
                                    }
                                    draw_text +: {
                                        color: theme.color_text
                                        color_empty: theme.color_text_meta
                                        text_style: theme.font_regular{font_size: 13}
                                    }
                                }
                                suggestion_label := Label{
                                    width: Fill height: 32
                                    margin: Inset{top: 24 left: 0 right: 0 bottom: 0}
                                    text: "FREQUENT"
                                    draw_text +: {
                                        color: theme.color_text_meta
                                        text_style: theme.font_bold{font_size: 9}
                                    }
                                }
                                suggest1 := ButtonFlatter{
                                    width: Fill height: 40 margin: 0
                                    text: "Wikipedia"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                suggest2 := ButtonFlatter{
                                    width: Fill height: 40 margin: 0
                                    text: "Hacker News"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                suggest3 := ButtonFlatter{
                                    width: Fill height: 40 margin: 0
                                    text: "GitHub"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                suggest4 := ButtonFlatter{
                                    width: Fill height: 40 margin: 0
                                    text: "DuckDuckGo"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                            }

                            settings_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 0
                                padding: Inset{left: 24 right: 24 top: 24 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app

                                settings_header := View{
                                    width: Fill height: 44
                                    flow: Right spacing: 8
                                    align: Align{x: 0.0 y: 0.5}
                                    settings_title := Label{
                                        width: Fill height: 44
                                        text: "Settings"
                                        draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 16}}
                                    }
                                    settings_close := ButtonFlatterIcon{
                                        width: 36 height: 36
                                        margin: 0
                                        draw_icon.svg: crate_resource("self:resources/icons/close.svg")
                                        draw_icon.color: theme.color_text_meta
                                        icon_walk: Walk{width: 16 height: Fit}
                                    }
                                }
                                settings_rule := View{
                                    width: Fill height: 1
                                    show_bg: true
                                    draw_bg.color: theme.color_bevel_outset_1
                                }
                                theme_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Theme"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                accent_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Accent"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                rail_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Rail width"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                labels_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Site labels"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                engine_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Search engine"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                motion_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Motion"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                sites_row := ButtonFlatter{
                                    width: Fill height: 48 margin: 0
                                    text: "Edit site rail"
                                    align: Align{x: 0.0 y: 0.5}
                                    draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}
                                }
                                settings_note := Label{
                                    width: Fill height: 48
                                    text: "Tap a row to change it. Your choices are saved on this device."
                                    draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}
                                }
                            }

                            history_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 0
                                padding: Inset{left: 24 right: 24 top: 24 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app

                                history_header := View{
                                    width: Fill height: 44
                                    flow: Right spacing: 8
                                    align: Align{x: 0.0 y: 0.5}
                                    history_title := Label{
                                        width: Fill height: 44
                                        text: "History"
                                        draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 16}}
                                    }
                                    history_clear := ButtonFlatter{
                                        width: 64 height: 36 margin: 0
                                        text: "Clear"
                                        draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 11}}
                                    }
                                    history_close := ButtonFlatterIcon{
                                        width: 36 height: 36
                                        margin: 0
                                        draw_icon.svg: crate_resource("self:resources/icons/close.svg")
                                        draw_icon.color: theme.color_text_meta
                                        icon_walk: Walk{width: 16 height: Fit}
                                    }
                                }
                                history_rule := View{
                                    width: Fill height: 1
                                    show_bg: true
                                    draw_bg.color: theme.color_bevel_outset_1
                                }
                                hist1 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                                hist2 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                                hist3 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                                hist4 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                                hist5 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                                hist6 := ButtonFlatter{width: Fill height: 44 margin: 0 text: "—" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 12}}}
                            }

                            sites_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 0
                                padding: Inset{left: 24 right: 24 top: 24 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app

                                sites_header := View{
                                    width: Fill height: 44
                                    flow: Right spacing: 8
                                    align: Align{x: 0.0 y: 0.5}
                                    sites_title := Label{
                                        width: Fill height: 44
                                        text: "Site rail"
                                        draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 16}}
                                    }
                                    sites_close := ButtonFlatterIcon{
                                        width: 36 height: 36
                                        margin: 0
                                        draw_icon.svg: crate_resource("self:resources/icons/close.svg")
                                        draw_icon.color: theme.color_text_meta
                                        icon_walk: Walk{width: 16 height: Fit}
                                    }
                                }
                                sites_note := Label{
                                    width: Fill height: 32
                                    text: "Choose a tile, enter an address, then Save."
                                    draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}
                                }
                                site_row1 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "1 · Wikipedia" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_row2 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "2 · Hacker News" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_row3 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "3 · GitHub" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_row4 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "4 · DuckDuckGo" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_row5 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "5 · YouTube" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_row6 := ButtonFlatter{width: Fill height: 34 margin: 0 text: "6 · Internet Archive" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                site_input := TextInput{
                                    width: Fill height: 44
                                    margin: Inset{top: 12 left: 0 right: 0 bottom: 0}
                                    empty_text: "https://example.com"
                                    draw_bg +: {
                                        color: theme.color_inset
                                        color_focus: theme.color_inset
                                        border_size: 0
                                        border_radius: 8
                                    }
                                    draw_text +: {
                                        color: theme.color_text
                                        color_empty: theme.color_text_meta
                                        text_style: theme.font_regular{font_size: 12}
                                    }
                                }
                                site_actions := View{
                                    width: Fill height: 44
                                    flow: Right spacing: 8
                                    align: Align{x: 0.0 y: 0.5}
                                    site_save := ButtonFlatter{width: 96 height: 36 margin: 0 text: "Save" draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                    site_default := ButtonFlatter{width: 96 height: 36 margin: 0 text: "Reset tile" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 11}}}
                                    site_all_default := ButtonFlatter{width: Fill height: 36 margin: 0 text: "Reset all" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 11}}}
                                }
                            }

                            search_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 0
                                padding: Inset{left: 24 right: 24 top: 24 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app

                                search_header := View{
                                    width: Fill height: 44
                                    flow: Right spacing: 8
                                    align: Align{x: 0.0 y: 0.5}
                                    search_title := Label{
                                        width: Fill height: 44
                                        text: "Slate Search"
                                        draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 16}}
                                    }
                                    search_close := ButtonFlatterIcon{
                                        width: 36 height: 36
                                        margin: 0
                                        draw_icon.svg: crate_resource("self:resources/icons/close.svg")
                                        draw_icon.color: theme.color_text_meta
                                        icon_walk: Walk{width: 16 height: Fit}
                                    }
                                }
                                search_query := Label{
                                    width: Fill height: 28
                                    text: ""
                                    draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 11}}
                                }
                                search_status := Label{
                                    width: Fill height: 24
                                    text: ""
                                    draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}
                                }
                                search_rule := View{
                                    width: Fill height: 1
                                    show_bg: true
                                    draw_bg.color: theme.color_bevel_outset_1
                                }
                                result1 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result2 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result3 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result4 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result5 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result6 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result7 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                                result8 := ButtonFlatter{width: Fill height: 46 margin: 0 text: "" align: Align{x: 0.0 y: 0.5} draw_text +: {color: theme.color_text text_style: theme.font_regular{font_size: 11}}}
                            }
                        }
                    }

                    rail := View{
                        width: 64 height: Fill
                        flow: Down
                        spacing: 4
                        padding: Inset{left: 8 right: 8 top: 12 bottom: 12}
                        show_bg: true
                        draw_bg.color: theme.color_bg_container

                        site1_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site1 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav1 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=en.wikipedia.org&sz=64")}
                            site1_label := Label{visible: false width: Fill height: 12 text: "Wiki" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }
                        site2_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site2 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav2 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=news.ycombinator.com&sz=64")}
                            site2_label := Label{visible: false width: Fill height: 12 text: "HN" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }
                        site3_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site3 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav3 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=github.com&sz=64")}
                            site3_label := Label{visible: false width: Fill height: 12 text: "Git" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }
                        site4_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site4 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav4 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64")}
                            site4_label := Label{visible: false width: Fill height: 12 text: "DDG" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }
                        site5_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site5 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav5 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=www.youtube.com&sz=64")}
                            site5_label := Label{visible: false width: Fill height: 12 text: "YT" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }
                        site6_tile := View{width: Fill height: 48 flow: Overlay align: Align{x: 0.5 y: 0.5}
                            site6 := ButtonFlatterIcon{
                                width: 40 height: 40 margin: 0 align: Center
                                draw_icon.svg: crate_resource("self:resources/icons/globe.svg")
                                draw_icon.color: theme.color_text_meta
                                icon_walk: Walk{width: 20 height: Fit}
                            }
                            fav6 := Image{width: 24 height: 24 fit: ImageFit.Smallest src: http_resource("https://www.google.com/s2/favicons?domain=archive.org&sz=64")}
                            site6_label := Label{visible: false width: Fill height: 12 text: "Arc" align: Align{x: 0.5 y: 1.0} draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 8}}}
                        }

                        rail_gap := View{width: Fill height: Fill}
                        rail_history := ButtonFlatterIcon{
                            width: 40 height: 40 margin: 0 align: Center
                            draw_icon.svg: crate_resource("self:resources/icons/history.svg")
                            draw_icon.color: theme.color_text_meta
                            icon_walk: Walk{width: 18 height: Fit}
                        }
                        rail_settings := ButtonFlatterIcon{
                            width: 40 height: 40 margin: 0 align: Center
                            draw_icon.svg: crate_resource("self:resources/icons/settings.svg")
                            draw_icon.color: theme.color_text_meta
                            icon_walk: Walk{width: 18 height: Fit}
                        }
                    }
                }
            }
        }
    }
}

#[derive(Script, ScriptHook)]
pub struct App {
    #[live]
    ui: WidgetRef,
    #[rust]
    settings: Settings,
    #[rust]
    surface: Surface,
    #[rust]
    editing_site: usize,
    #[rust]
    search_query: String,
    #[rust]
    search_return: Surface,
    #[rust]
    search_results: Vec<SearchResult>,
    #[rust]
    search_groups: Vec<Vec<SearchResult>>,
    #[rust]
    search_requests: Vec<(LiveId, usize)>,
    #[rust]
    search_failed: usize,
    #[rust]
    load_id: Option<StorageRequestId>,
    #[rust]
    save_id: Option<StorageRequestId>,
}

impl App {
    fn web(&self, cx: &mut Cx) -> makepad_widgets::WebViewRef {
        self.ui.web_view(cx, ids!(page))
    }

    fn set_surface(&mut self, cx: &mut Cx, surface: Surface) {
        self.surface = surface;
        self.ui
            .widget(cx, ids!(start))
            .set_visible(cx, surface == Surface::Start);
        self.ui
            .widget(cx, ids!(settings_panel))
            .set_visible(cx, surface == Surface::Settings);
        self.ui
            .widget(cx, ids!(history_panel))
            .set_visible(cx, surface == Surface::History);
        self.ui
            .widget(cx, ids!(sites_panel))
            .set_visible(cx, surface == Surface::Sites);
        self.ui
            .widget(cx, ids!(search_panel))
            .set_visible(cx, surface == Surface::Search);
        self.web(cx).set_visible(cx, surface == Surface::Page);
        if surface == Surface::Start {
            self.web(cx).blur(cx);
        }
        let state = self.web(cx).state();
        self.refresh_nav_state(cx, state.can_go_back, state.can_go_forward);
    }

    fn default_surface(&self) -> Surface {
        if self.settings.tabs[self.settings.active].is_empty() {
            Surface::Start
        } else {
            Surface::Page
        }
    }

    fn close_panels(&mut self, cx: &mut Cx) {
        let surface = self.default_surface();
        self.set_surface(cx, surface);
    }

    fn refresh_tabs(&self, cx: &mut Cx, animate: bool) {
        let marks = [ids!(tab1_mark), ids!(tab2_mark), ids!(tab3_mark)];
        for (i, id) in marks.into_iter().enumerate() {
            let mark = self.ui.view(cx, id);
            let state = if i == self.settings.active {
                ids!(active.on)
            } else {
                ids!(active.off)
            };
            if animate && !self.settings.reduced_motion {
                mark.animator_play(cx, state);
            } else {
                mark.animator_cut(cx, state);
            }
        }
    }

    fn refresh_tab_titles(&self, cx: &mut Cx) {
        let tabs = [ids!(tab1), ids!(tab2), ids!(tab3)];
        for (i, id) in tabs.into_iter().enumerate() {
            let title = tab_label(&self.settings.tabs[i], i);
            self.ui.button(cx, id).set_text(cx, &title);
        }
    }

    fn refresh_nav_state(&self, cx: &mut Cx, can_back: bool, can_forward: bool) {
        let enabled = self.surface == Surface::Page;
        self.ui.button(cx, ids!(back)).set_enabled(cx, enabled && can_back);
        self.ui
            .button(cx, ids!(forward))
            .set_enabled(cx, enabled && can_forward);
    }

    fn set_loading(&self, cx: &mut Cx, loading: bool) {
        self.ui.widget(cx, ids!(load_bar)).set_visible(cx, loading);
    }

    fn refresh_rail(&self, cx: &mut Cx) {
        let labels = [
            ids!(site1_label),
            ids!(site2_label),
            ids!(site3_label),
            ids!(site4_label),
            ids!(site5_label),
            ids!(site6_label),
        ];
        let favicons = [ids!(fav1), ids!(fav2), ids!(fav3), ids!(fav4), ids!(fav5), ids!(fav6)];
        for (i, (label_id, fav_id)) in labels.into_iter().zip(favicons).enumerate() {
            let site = &self.settings.sites[i];
            self.ui.label(cx, label_id).set_text(cx, &site.label);
            self.ui
                .widget(cx, label_id)
                .set_visible(cx, site.custom || self.settings.labels);
            self.ui.widget(cx, fav_id).set_visible(cx, !site.custom);
        }
    }

    fn refresh_sites(&self, cx: &mut Cx) {
        let rows = [
            ids!(site_row1),
            ids!(site_row2),
            ids!(site_row3),
            ids!(site_row4),
            ids!(site_row5),
            ids!(site_row6),
        ];
        for (i, id) in rows.into_iter().enumerate() {
            let marker = if i == self.editing_site { "›" } else { " " };
            let text = format!("{} {} · {}", marker, i + 1, self.settings.sites[i].label);
            self.ui.button(cx, id).set_text(cx, &text);
        }
        let url = self.settings.sites[self.editing_site].url.clone();
        self.ui.text_input(cx, ids!(site_input)).set_text(cx, &url);
    }

    fn normalize_url(&self, input: &str) -> String {
        let value = input.trim();
        if value.is_empty() {
            return String::new();
        }
        if value.starts_with("http://")
            || value.starts_with("https://")
            || value.starts_with("data:")
            || value.starts_with("file:")
        {
            return value.to_string();
        }
        let host = value.split('/').next().unwrap_or(value);
        if host.contains('.') && !host.contains(' ') {
            return format!("https://{value}");
        }
        String::new()
    }

    fn is_web_address(&self, input: &str) -> bool {
        !self.normalize_url(input).is_empty()
    }

    fn push_history(&mut self, url: String) {
        if url.is_empty() {
            return;
        }
        self.settings.history.retain(|item| item != &url);
        self.settings.history.insert(0, url);
        self.settings.history.truncate(24);
    }

    fn navigate(&mut self, cx: &mut Cx, input: &str) {
        let url = self.normalize_url(input);
        if url.is_empty() {
            return;
        }
        self.settings.tabs[self.settings.active] = url.clone();
        self.push_history(url.clone());
        self.set_surface(cx, Surface::Page);
        self.web(cx).set_url(cx, &url);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
        self.set_loading(cx, true);
        self.refresh_tab_titles(cx);
        self.refresh_history(cx);
        self.persist(cx);
    }

    fn submit(&mut self, cx: &mut Cx, input: &str) {
        let value = input.trim();
        if value.is_empty() {
            return;
        }
        if self.is_web_address(value) {
            self.navigate(cx, value);
        } else {
            self.start_search(cx, value);
        }
    }

    fn refresh_search(&self, cx: &mut Cx, searching: bool, status: &str) {
        self.ui
            .label(cx, ids!(search_query))
            .set_text(cx, &self.search_query);
        self.ui
            .label(cx, ids!(search_status))
            .set_text(cx, status);
        let ids = [
            ids!(result1),
            ids!(result2),
            ids!(result3),
            ids!(result4),
            ids!(result5),
            ids!(result6),
            ids!(result7),
            ids!(result8),
        ];
        for (i, id) in ids.into_iter().enumerate() {
            let button = self.ui.button(cx, id);
            if let Some(result) = self.search_results.get(i) {
                let text = format!("{} · {}", result.title, SEARCH_SOURCES[result.source].0);
                button.set_text(cx, &text);
                button.set_enabled(cx, true);
            } else {
                button.set_text(cx, "");
                button.set_enabled(cx, false);
            }
        }
        let _ = searching;
    }

    fn start_search(&mut self, cx: &mut Cx, query: &str) {
        self.search_query = query.trim().to_string();
        self.search_return = self.surface;
        self.search_results.clear();
        self.search_groups = vec![Vec::new(); SEARCH_SOURCES.len()];
        self.search_requests.clear();
        self.search_failed = 0;
        self.set_surface(cx, Surface::Search);
        self.set_loading(cx, false);
        self.ui
            .text_input(cx, ids!(omnibox))
            .set_text(cx, &self.search_query);
        self.refresh_search(cx, true, "Searching DuckDuckGo and Bing…");

        for (source, url) in search_source_urls(&self.search_query, self.settings.engine) {
            let request_id = LiveId::unique();
            let mut request = HttpRequest::new(url, HttpMethod::GET);
            request.set_header(
                "User-Agent".to_string(),
                SEARCH_USER_AGENT.to_string(),
            );
            cx.http_request(request_id, request);
            self.search_requests.push((request_id, source));
        }
    }

    fn close_search(&mut self, cx: &mut Cx) {
        let surface = self.search_return;
        self.set_surface(cx, surface);
    }

    fn on_network(&mut self, cx: &mut Cx, responses: &[NetworkResponse]) {
        if self.surface != Surface::Search || self.search_requests.is_empty() {
            return;
        }
        for item in responses {
            let (request_id, body) = match item {
                NetworkResponse::HttpResponse { request_id, response } => {
                    (*request_id, response.get_string_body())
                }
                NetworkResponse::HttpError { request_id, .. } => (*request_id, None),
                _ => continue,
            };
            let Some(position) = self
                .search_requests
                .iter()
                .position(|(id, _)| *id == request_id)
            else {
                continue;
            };
            let (_, source) = self.search_requests.remove(position);
            match body {
                Some(html) => {
                    self.search_groups[source] = parse_search_results(source, &html);
                }
                None => self.search_failed += 1,
            }
        }
        if self.search_requests.is_empty() {
            self.search_results = merge_search_results(&self.search_groups);
            let status = if self.search_results.is_empty() {
                if self.search_failed > 0 {
                    "Search sources are unavailable. Check the connection and try again."
                        .to_string()
                } else {
                    "No results found. Try a shorter query.".to_string()
                }
            } else {
                format!(
                    "{} results · {}",
                    self.search_results.len(),
                    SOURCE_PRESETS[self.settings.engine as usize]
                )
            };
            self.refresh_search(cx, false, &status);
        }
    }

    fn go_home(&mut self, cx: &mut Cx) {
        self.set_surface(cx, Surface::Start);
        self.set_loading(cx, false);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        self.ui.text_input(cx, ids!(start_search)).set_text(cx, "");
    }

    fn switch_tab(&mut self, cx: &mut Cx, index: usize) {
        self.settings.active = index;
        self.refresh_tabs(cx, true);
        self.set_loading(cx, false);
        let url = self.settings.tabs[index].clone();
        if url.is_empty() {
            self.set_surface(cx, Surface::Start);
            self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        } else {
            self.set_surface(cx, Surface::Page);
            self.web(cx).set_url(cx, &url);
            self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
            self.set_loading(cx, true);
        }
        self.refresh_tab_titles(cx);
        self.persist(cx);
    }

    fn refresh_history(&self, cx: &mut Cx) {
        let names = [
            ids!(hist1),
            ids!(hist2),
            ids!(hist3),
            ids!(hist4),
            ids!(hist5),
            ids!(hist6),
        ];
        for (i, id) in names.into_iter().enumerate() {
            let text = self
                .settings
                .history
                .get(i)
                .map(|url| {
                    let short = url.trim_start_matches("https://").trim_start_matches("http://");
                    if short.len() > 42 {
                        format!("{}…", &short[..42])
                    } else {
                        short.to_string()
                    }
                })
                .unwrap_or_else(|| {
                    if i == 0 {
                        "No history yet — visited pages appear here".to_string()
                    } else {
                        String::new()
                    }
                });
            let button = self.ui.button(cx, id);
            button.set_text(cx, &text);
            button.set_enabled(cx, self.settings.history.get(i).is_some());
        }
    }

    fn refresh_settings(&self, cx: &mut Cx) {
        let values = [
            (
                ids!(theme_row),
                format!("Theme  ·  {}", THEMES[self.settings.theme as usize]),
            ),
            (
                ids!(accent_row),
                format!("Accent  ·  {}", ACCENTS[self.settings.accent as usize]),
            ),
            (
                ids!(rail_row),
                format!("Rail width  ·  {:.0} dp", RAIL_WIDTHS[self.settings.rail as usize]),
            ),
            (
                ids!(labels_row),
                format!("Site labels  ·  {}", if self.settings.labels { "On" } else { "Off" }),
            ),
            (
                ids!(engine_row),
                format!("Search sources  ·  {}", SOURCE_PRESETS[self.settings.engine as usize]),
            ),
            (
                ids!(motion_row),
                format!(
                    "Motion  ·  {}",
                    if self.settings.reduced_motion { "Reduced" } else { "Subtle" }
                ),
            ),
            (ids!(sites_row), "Edit site rail".to_string()),
        ];
        for (id, text) in values {
            self.ui.button(cx, id).set_text(cx, &text);
        }
    }

    fn apply_appearance(&mut self, cx: &mut Cx) {
        match self.settings.theme {
            0 => { script_eval!(cx, {mod.theme = mod.themes.dark true}); }
            1 => { script_eval!(cx, {mod.theme = mod.themes.light true}); }
            _ => { script_eval!(cx, {mod.theme = mod.themes.skeleton true}); }
        }
        match self.settings.accent {
            0 => { script_eval!(cx, {mod.theme.color_focus = #9FC5E8FF true}); }
            1 => { script_eval!(cx, {mod.theme.color_focus = #C89B78FF true}); }
            _ => { script_eval!(cx, {mod.theme.color_focus = #8FB69AFF true}); }
        }
        let width = RAIL_WIDTHS[self.settings.rail as usize];
        self.ui.view(cx, ids!(rail)).set_walk(
            cx,
            Walk {
                width: Size::Fixed(width),
                height: Size::fill(),
                ..Walk::default()
            },
        );
        self.refresh_rail(cx);
        self.refresh_tabs(cx, false);
        self.refresh_tab_titles(cx);
        self.refresh_sites(cx);
        self.refresh_settings(cx);
        self.refresh_history(cx);
    }

    fn load(&mut self, cx: &mut Cx) {
        let storage = cx.storage("slate-browser");
        self.load_id = Some(storage.get(cx, "state"));
    }

    fn persist(&mut self, cx: &mut Cx) {
        let storage = cx.storage("slate-browser");
        self.save_id = Some(storage.set(cx, "state", self.settings.encode().into_bytes()));
    }

    fn on_storage(&mut self, cx: &mut Cx, responses: &[StorageResponse]) {
        for response in responses {
            if self.load_id == Some(response.request_id) {
                self.load_id = None;
                if let Ok(StorageResult::Value(Some(bytes))) = &response.result {
                    if let Ok(text) = std::str::from_utf8(bytes) {
                        if let Some(settings) = Settings::decode(text) {
                            self.settings = settings;
                        }
                    }
                }
                self.apply_appearance(cx);
                self.set_loading(cx, false);
                let surface = self.default_surface();
                self.set_surface(cx, surface);
                if surface == Surface::Page {
                    let url = self.settings.tabs[self.settings.active].clone();
                    self.web(cx).set_url(cx, &url);
                    self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
                }
            }
            if self.save_id == Some(response.request_id) {
                self.save_id = None;
            }
        }
    }
}

macro_rules! site_click {
    ($self:expr, $cx:expr, $actions:expr, $id:ident, $index:expr) => {
        if $self.ui.button($cx, ids!($id)).clicked($actions) {
            let url = $self.settings.sites[$index].url.clone();
            $self.navigate($cx, &url);
        }
    };
}

macro_rules! suggest_click {
    ($self:expr, $cx:expr, $actions:expr, $id:ident, $index:expr) => {
        if $self.ui.button($cx, ids!($id)).clicked($actions) {
            $self.navigate($cx, SITES[$index].1);
        }
    };
}

impl MatchEvent for App {
    fn handle_actions(&mut self, cx: &mut Cx, actions: &Actions) {
        let omnibox = self.ui.text_input(cx, ids!(omnibox));
        if let Some((text, _)) = omnibox.returned(actions) {
            let text = text.clone();
            self.submit(cx, &text);
        }
        let start_search = self.ui.text_input(cx, ids!(start_search));
        if let Some((text, _)) = start_search.returned(actions) {
            let text = text.clone();
            self.submit(cx, &text);
        }
        if self.ui.button(cx, ids!(search_go)).clicked(actions) {
            let text = self.ui.text_input(cx, ids!(omnibox)).text();
            self.submit(cx, &text);
        }

        if self.ui.button(cx, ids!(back)).clicked(actions) {
            self.web(cx).history(cx, -1);
        }
        if self.ui.button(cx, ids!(forward)).clicked(actions) {
            self.web(cx).history(cx, 1);
        }
        if self.ui.button(cx, ids!(reload)).clicked(actions) {
            self.web(cx).reload(cx);
        }
        if self.ui.button(cx, ids!(home)).clicked(actions) {
            self.go_home(cx);
        }
        if self.ui.button(cx, ids!(tab1)).clicked(actions) {
            self.switch_tab(cx, 0);
        }
        if self.ui.button(cx, ids!(tab2)).clicked(actions) {
            self.switch_tab(cx, 1);
        }
        if self.ui.button(cx, ids!(tab3)).clicked(actions) {
            self.switch_tab(cx, 2);
        }

        site_click!(self, cx, actions, site1, 0);
        site_click!(self, cx, actions, site2, 1);
        site_click!(self, cx, actions, site3, 2);
        site_click!(self, cx, actions, site4, 3);
        site_click!(self, cx, actions, site5, 4);
        site_click!(self, cx, actions, site6, 5);
        suggest_click!(self, cx, actions, suggest1, 0);
        suggest_click!(self, cx, actions, suggest2, 1);
        suggest_click!(self, cx, actions, suggest3, 2);
        suggest_click!(self, cx, actions, suggest4, 3);

        if self.ui.button(cx, ids!(rail_settings)).clicked(actions) {
            self.set_surface(cx, Surface::Settings);
            self.apply_appearance(cx);
        }
        if self.ui.button(cx, ids!(rail_history)).clicked(actions)
            || self.ui.button(cx, ids!(header_history)).clicked(actions)
        {
            self.refresh_history(cx);
            self.set_surface(cx, Surface::History);
        }
        if self.ui.button(cx, ids!(settings_close)).clicked(actions)
            || self.ui.button(cx, ids!(history_close)).clicked(actions)
            || self.ui.button(cx, ids!(sites_close)).clicked(actions)
        {
            self.close_panels(cx);
        }
        if self.ui.button(cx, ids!(search_close)).clicked(actions) {
            self.close_search(cx);
        }

        let result_ids = [
            ids!(result1),
            ids!(result2),
            ids!(result3),
            ids!(result4),
            ids!(result5),
            ids!(result6),
            ids!(result7),
            ids!(result8),
        ];
        for (i, id) in result_ids.into_iter().enumerate() {
            if self.ui.button(cx, id).clicked(actions) {
                if let Some(result) = self.search_results.get(i).cloned() {
                    self.navigate(cx, &result.url);
                }
                break;
            }
        }

        if self.ui.button(cx, ids!(history_clear)).clicked(actions) {
            self.settings.history.clear();
            self.refresh_history(cx);
            self.persist(cx);
        }

        if self.ui.button(cx, ids!(theme_row)).clicked(actions) {
            self.settings.theme = (self.settings.theme + 1) % 3;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(accent_row)).clicked(actions) {
            self.settings.accent = (self.settings.accent + 1) % 3;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(rail_row)).clicked(actions) {
            self.settings.rail = (self.settings.rail + 1) % 3;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(labels_row)).clicked(actions) {
            self.settings.labels = !self.settings.labels;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(engine_row)).clicked(actions) {
            self.settings.engine = (self.settings.engine + 1) % 3;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(motion_row)).clicked(actions) {
            self.settings.reduced_motion = !self.settings.reduced_motion;
            self.apply_appearance(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(sites_row)).clicked(actions) {
            self.refresh_sites(cx);
            self.set_surface(cx, Surface::Sites);
        }

        let site_rows = [
            ids!(site_row1),
            ids!(site_row2),
            ids!(site_row3),
            ids!(site_row4),
            ids!(site_row5),
            ids!(site_row6),
        ];
        for (i, id) in site_rows.into_iter().enumerate() {
            if self.ui.button(cx, id).clicked(actions) {
                self.editing_site = i;
                self.refresh_sites(cx);
                break;
            }
        }
        if self.ui.button(cx, ids!(site_save)).clicked(actions) {
            let typed = self.ui.text_input(cx, ids!(site_input)).text();
            let url = self.normalize_url(&typed);
            if !url.is_empty() {
                let label = site_label_from_url(&url);
                if let Some(slot) = self.settings.sites.get_mut(self.editing_site) {
                    *slot = Site {
                        label,
                        url,
                        custom: true,
                    };
                }
                self.refresh_rail(cx);
                self.refresh_sites(cx);
                self.persist(cx);
            }
        }
        if self.ui.button(cx, ids!(site_default)).clicked(actions) {
            if let Some(slot) = self.settings.sites.get_mut(self.editing_site) {
                *slot = Site::default_site(self.editing_site);
            }
            self.refresh_rail(cx);
            self.refresh_sites(cx);
            self.persist(cx);
        }
        if self.ui.button(cx, ids!(site_all_default)).clicked(actions) {
            self.settings.sites = (0..SITES.len()).map(Site::default_site).collect();
            self.refresh_rail(cx);
            self.refresh_sites(cx);
            self.persist(cx);
        }

        let hist_ids = [
            ids!(hist1),
            ids!(hist2),
            ids!(hist3),
            ids!(hist4),
            ids!(hist5),
            ids!(hist6),
        ];
        for (i, id) in hist_ids.into_iter().enumerate() {
            if self.ui.button(cx, id).clicked(actions) {
                if let Some(url) = self.settings.history.get(i).cloned() {
                    self.navigate(cx, &url);
                }
                break;
            }
        }

        let page_uid = self.ui.widget(cx, ids!(page)).widget_uid();
        for action in actions {
            let Some(widget_action) = action.as_widget_action() else {
                continue;
            };
            if widget_action.widget_uid != page_uid {
                continue;
            }
            match widget_action.cast::<WebViewAction>() {
                WebViewAction::Url(url) => {
                    self.settings.tabs[self.settings.active] = url.clone();
                    self.push_history(url.clone());
                    self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
                    self.refresh_tab_titles(cx);
                    self.refresh_history(cx);
                    self.persist(cx);
                }
                WebViewAction::Nav { can_back, can_forward } => {
                    self.refresh_nav_state(cx, can_back, can_forward);
                }
                WebViewAction::Loading(loading) => {
                    self.set_loading(cx, loading);
                }
                _ => {}
            }
        }
    }
}

impl AppMain for App {
    fn script_mod(vm: &mut ScriptVm) -> ScriptValue {
        makepad_widgets::script_mod(vm);
        self::script_mod(vm)
    }

    fn handle_event(&mut self, cx: &mut Cx, event: &Event) {
        if let Event::Storage(responses) = event {
            self.on_storage(cx, responses);
        }
        if let Event::NetworkResponses(responses) = event {
            self.on_network(cx, responses);
        }
        if let Event::Startup = event {
            self.load(cx);
            self.set_surface(cx, Surface::Start);
        }
        if matches!(event, Event::BackPressed { .. }) {
            if event.back_pressed() {
                if self.surface == Surface::Search {
                    self.close_search(cx);
                } else if self.surface != Surface::Page && self.surface != Surface::Start {
                    self.close_panels(cx);
                } else if self.web(cx).state().can_go_back {
                    self.web(cx).history(cx, -1);
                } else {
                    self.go_home(cx);
                }
                return;
            }
        }
        self.match_event(cx, event);
        self.ui.handle_event(cx, event, &mut Scope::empty());
    }
}
