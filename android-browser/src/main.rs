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

app_main!(App);

const SITES: [(&str, &str, &str); 6] = [
    ("W", "Wikipedia", "https://en.wikipedia.org"),
    ("H", "Hacker News", "https://news.ycombinator.com"),
    ("G", "GitHub", "https://github.com"),
    ("D", "DuckDuckGo", "https://duckduckgo.com"),
    ("Y", "YouTube", "https://www.youtube.com"),
    ("A", "Internet Archive", "https://archive.org"),
];

const ENGINES: [(&str, &str); 3] = [
    ("DuckDuckGo", "https://duckduckgo.com/?q="),
    ("Bing", "https://www.bing.com/search?q="),
    ("Google", "https://www.google.com/search?q="),
];

const THEMES: [&str; 3] = ["Moon dark", "Paper light", "Skeleton"];
const ACCENTS: [&str; 3] = ["Ice", "Copper", "Moss"];
const RAIL_WIDTHS: [f64; 3] = [64.0, 72.0, 84.0];

#[derive(Clone, Copy, Debug, PartialEq)]
enum Surface {
    Start,
    Page,
    Settings,
    History,
}

impl Default for Surface {
    fn default() -> Self {
        Self::Start
    }
}

#[derive(Clone, Debug)]
struct Settings {
    theme: u8,
    accent: u8,
    rail: u8,
    labels: bool,
    engine: u8,
    tabs: [String; 3],
    active: usize,
    history: Vec<String>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            theme: 0,
            accent: 0,
            rail: 0,
            labels: false,
            engine: 0,
            tabs: [String::new(), String::new(), String::new()],
            active: 0,
            history: Vec::new(),
        }
    }
}

impl Settings {
    fn encode(&self) -> String {
        let mut out = String::from("slate-v1\n");
        out.push_str(&format!("theme={}\n", self.theme));
        out.push_str(&format!("accent={}\n", self.accent));
        out.push_str(&format!("rail={}\n", self.rail));
        out.push_str(&format!("labels={}\n", u8::from(self.labels)));
        out.push_str(&format!("engine={}\n", self.engine));
        out.push_str(&format!("active={}\n", self.active));
        for (i, tab) in self.tabs.iter().enumerate() {
            if !tab.is_empty() {
                out.push_str(&format!("tab={i}|{tab}\n"));
            }
        }
        for url in self.history.iter().take(24) {
            out.push_str(&format!("hist={url}\n"));
        }
        out
    }

    fn decode(text: &str) -> Option<Self> {
        if !text.starts_with("slate-v1") {
            return None;
        }
        let mut s = Self::default();
        for line in text.lines().skip(1) {
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
            }
        }
        Some(s)
    }
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
        self.web(cx).set_visible(cx, surface == Surface::Page);
        if surface == Surface::Start {
            self.web(cx).blur(cx);
        }
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
            if animate {
                mark.animator_play(cx, state);
            } else {
                mark.animator_cut(cx, state);
            }
        }
    }

    fn resolve(&self, input: &str) -> String {
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
        format!("{}{}", ENGINES[self.settings.engine as usize].1, percent_encode(value))
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
        let url = self.resolve(input);
        if url.is_empty() {
            return;
        }
        self.settings.tabs[self.settings.active] = url.clone();
        self.push_history(url.clone());
        self.set_surface(cx, Surface::Page);
        self.web(cx).set_url(cx, &url);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
        self.refresh_history(cx);
        self.persist(cx);
    }

    fn go_home(&mut self, cx: &mut Cx) {
        self.set_surface(cx, Surface::Start);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        self.ui.text_input(cx, ids!(start_search)).set_text(cx, "");
    }

    fn switch_tab(&mut self, cx: &mut Cx, index: usize) {
        self.settings.active = index;
        self.refresh_tabs(cx, true);
        let url = self.settings.tabs[index].clone();
        if url.is_empty() {
            self.set_surface(cx, Surface::Start);
            self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        } else {
            self.set_surface(cx, Surface::Page);
            self.web(cx).set_url(cx, &url);
            self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
        }
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
                .unwrap_or_else(|| "—".to_string());
            self.ui.button(cx, id).set_text(cx, &text);
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
                format!("Search engine  ·  {}", ENGINES[self.settings.engine as usize].0),
            ),
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
        let labels = [
            ids!(site1_label),
            ids!(site2_label),
            ids!(site3_label),
            ids!(site4_label),
            ids!(site5_label),
            ids!(site6_label),
        ];
        for id in labels {
            self.ui.widget(cx, id).set_visible(cx, self.settings.labels);
        }
        self.refresh_tabs(cx, false);
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
            $self.navigate($cx, SITES[$index].2);
        }
    };
}

impl MatchEvent for App {
    fn handle_actions(&mut self, cx: &mut Cx, actions: &Actions) {
        let omnibox = self.ui.text_input(cx, ids!(omnibox));
        if let Some((text, _)) = omnibox.returned(actions) {
            let text = text.clone();
            self.navigate(cx, &text);
        }
        let start_search = self.ui.text_input(cx, ids!(start_search));
        if let Some((text, _)) = start_search.returned(actions) {
            let text = text.clone();
            self.navigate(cx, &text);
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
        site_click!(self, cx, actions, suggest1, 0);
        site_click!(self, cx, actions, suggest2, 1);
        site_click!(self, cx, actions, suggest3, 2);
        site_click!(self, cx, actions, suggest4, 3);

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
        {
            self.close_panels(cx);
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
                    self.refresh_history(cx);
                    self.persist(cx);
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
        if let Event::Startup = event {
            self.load(cx);
            self.set_surface(cx, Surface::Start);
        }
        if matches!(event, Event::BackPressed { .. }) {
            if event.back_pressed() {
                if self.surface != Surface::Page && self.surface != Surface::Start {
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
