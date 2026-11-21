//! Slate Browser — a Rust browser with a full-height site rail.
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
            rail: 1,
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
                s.rail = value.parse().unwrap_or(1).min(2);
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

                    work := View{
                        width: Fill
                        height: Fill
                        flow: Down
                        spacing: 0
                        show_bg: true
                        draw_bg.color: theme.color_bg_app

                        tabs := View{
                            width: Fill
                            height: 48
                            flow: Right
                            spacing: 4
                            padding: Inset{left: 8 right: 8 top: 6 bottom: 2}
                            tab1 := Button{width: 64 height: 36 text: "1" draw_text +: {color: theme.color_text_meta text_style: theme.font_bold{font_size: 11}}}
                            tab2 := Button{width: 64 height: 36 text: "2" draw_text +: {color: theme.color_text_meta text_style: theme.font_bold{font_size: 11}}}
                            tab3 := Button{width: 64 height: 36 text: "3" draw_text +: {color: theme.color_text_meta text_style: theme.font_bold{font_size: 11}}}
                            tab_gap := View{width: Fill height: Fill}
                            tab_add := ButtonFlatterIcon{
                                width: 36 height: 36
                                draw_icon.svg: crate_resource("self:resources/icons/close.svg")
                                draw_icon.color: theme.color_text_meta
                            }
                        }

                        toolbar := View{
                            width: Fill
                            height: 64
                            flow: Right
                            spacing: 4
                            padding: Inset{left: 10 right: 10 top: 6 bottom: 6}
                            show_bg: true
                            draw_bg.color: theme.color_bg_container
                            back := ButtonFlatterIcon{
                                width: 44 height: 44
                                draw_icon.svg: crate_resource("self:resources/icons/back.svg")
                                draw_icon.color: theme.color_text
                            }
                            forward := ButtonFlatterIcon{
                                width: 44 height: 44
                                draw_icon.svg: crate_resource("self:resources/icons/forward.svg")
                                draw_icon.color: theme.color_text
                            }
                            reload := ButtonFlatterIcon{
                                width: 44 height: 44
                                draw_icon.svg: crate_resource("self:resources/icons/reload.svg")
                                draw_icon.color: theme.color_text
                            }
                            omnibox := TextInput{
                                width: Fill height: 44
                                empty_text: "Search or address"
                                draw_bg +: {
                                    color: theme.color_inset
                                    color_focus: theme.color_inset
                                    border_size: 0
                                    border_radius: 10
                                }
                                draw_text +: {
                                    color: theme.color_text
                                    color_empty: theme.color_text_meta
                                    text_style: theme.font_regular{font_size: 12}
                                }
                            }
                            home := ButtonFlatterIcon{
                                width: 44 height: 44
                                draw_icon.svg: crate_resource("self:resources/icons/home.svg")
                                draw_icon.color: theme.color_focus
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
                                spacing: 12
                                align: Align{x: 0.5 y: 0.18}
                                padding: Inset{left: 24 right: 24 top: 72 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app
                                brand := Label{
                                    width: Fill height: 40
                                    text: "SLATE"
                                    align: Align{x: 0.5 y: 0.5}
                                    draw_text +: {
                                        color: theme.color_text
                                        text_style: theme.font_bold{font_size: 26}
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
                                    width: Fill height: 52
                                    margin: Inset{top: 24}
                                    empty_text: "Search or type an address"
                                    draw_bg +: {
                                        color: theme.color_inset
                                        color_focus: theme.color_inset
                                        border_size: 0
                                        border_radius: 12
                                    }
                                    draw_text +: {
                                        color: theme.color_text
                                        color_empty: theme.color_text_meta
                                        text_style: theme.font_regular{font_size: 13}
                                    }
                                }
                                suggestion_label := Label{
                                    width: Fill height: 24
                                    margin: Inset{top: 16}
                                    text: "Frequent"
                                    draw_text +: {
                                        color: theme.color_text_meta
                                        text_style: theme.font_bold{font_size: 9}
                                    }
                                }
                                suggest1 := Button{width: Fill height: 44 text: "Wikipedia"}
                                suggest2 := Button{width: Fill height: 44 text: "Hacker News"}
                                suggest3 := Button{width: Fill height: 44 text: "GitHub"}
                                suggest4 := Button{width: Fill height: 44 text: "DuckDuckGo"}
                            }

                            settings_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 4
                                padding: Inset{left: 24 right: 24 top: 28 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app
                                settings_title := Label{
                                    width: Fill height: 36
                                    text: "Settings"
                                    draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 19}}
                                }
                                theme_row := Button{width: Fill height: 48 text: "Theme"}
                                theme_value := Label{width: Fill height: 20 text: "Moon dark" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}}
                                accent_row := Button{width: Fill height: 48 text: "Accent"}
                                accent_value := Label{width: Fill height: 20 text: "Ice" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}}
                                rail_row := Button{width: Fill height: 48 text: "Rail width"}
                                rail_value := Label{width: Fill height: 20 text: "72" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}}
                                labels_row := Button{width: Fill height: 48 text: "Site labels"}
                                labels_value := Label{width: Fill height: 20 text: "Off" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}}
                                engine_row := Button{width: Fill height: 48 text: "Search engine"}
                                engine_value := Label{width: Fill height: 20 text: "DuckDuckGo" draw_text +: {color: theme.color_text_meta text_style: theme.font_regular{font_size: 10}}}
                                settings_close := Button{width: Fill height: 48 text: "Done"}
                            }

                            history_panel := View{
                                visible: false
                                width: Fill height: Fill
                                flow: Down
                                spacing: 4
                                padding: Inset{left: 24 right: 24 top: 28 bottom: 24}
                                show_bg: true
                                draw_bg.color: theme.color_bg_app
                                history_title := Label{
                                    width: Fill height: 36
                                    text: "History"
                                    draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 19}}
                                }
                                hist1 := Button{width: Fill height: 40 text: "—"}
                                hist2 := Button{width: Fill height: 40 text: "—"}
                                hist3 := Button{width: Fill height: 40 text: "—"}
                                hist4 := Button{width: Fill height: 40 text: "—"}
                                hist5 := Button{width: Fill height: 40 text: "—"}
                                hist6 := Button{width: Fill height: 40 text: "—"}
                                history_close := Button{width: Fill height: 48 text: "Done"}
                            }
                        }
                    }

                    rail := View{
                        width: 72 height: Fill
                        flow: Down
                        spacing: 4
                        padding: Inset{left: 6 right: 6 top: 12 bottom: 12}
                        show_bg: true
                        draw_bg.color: theme.color_bg_container

                        site1 := ButtonFlatter{width: 56 height: 56 text: "W" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        site2 := ButtonFlatter{width: 56 height: 56 text: "H" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        site3 := ButtonFlatter{width: 56 height: 56 text: "G" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        site4 := ButtonFlatter{width: 56 height: 56 text: "D" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        site5 := ButtonFlatter{width: 56 height: 56 text: "Y" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        site6 := ButtonFlatter{width: 56 height: 56 text: "A" draw_text +: {color: theme.color_text text_style: theme.font_bold{font_size: 15}}}
                        rail_gap := View{width: Fill height: Fill}
                        rail_history := ButtonFlatterIcon{
                            width: 56 height: 56
                            draw_icon.svg: crate_resource("self:resources/icons/history.svg")
                            draw_icon.color: theme.color_text_meta
                        }
                        rail_settings := ButtonFlatterIcon{
                            width: 56 height: 56
                            draw_icon.svg: crate_resource("self:resources/icons/settings.svg")
                            draw_icon.color: theme.color_text_meta
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
    load_id: Option<StorageRequestId>,
    #[rust]
    save_id: Option<StorageRequestId>,
}

impl App {
    fn web(&self, cx: &mut Cx) -> makepad_widgets::WebViewRef {
        self.ui.web_view(cx, ids!(page))
    }

    fn show_start(&mut self, cx: &mut Cx, show: bool) {
        self.ui.widget(cx, ids!(start)).set_visible(cx, show);
        self.web(cx).set_visible(cx, !show);
    }

    fn close_panels(&self, cx: &mut Cx) {
        self.ui.widget(cx, ids!(settings_panel)).set_visible(cx, false);
        self.ui.widget(cx, ids!(history_panel)).set_visible(cx, false);
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
        self.close_panels(cx);
        self.show_start(cx, false);
        self.web(cx).set_url(cx, &url);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, &url);
        self.refresh_history(cx);
        self.persist(cx);
    }

    fn go_home(&mut self, cx: &mut Cx) {
        self.close_panels(cx);
        self.show_start(cx, true);
        self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        self.ui.text_input(cx, ids!(start_search)).set_text(cx, "");
        self.web(cx).blur(cx);
    }

    fn switch_tab(&mut self, cx: &mut Cx, index: usize) {
        self.settings.active = index;
        let url = self.settings.tabs[index].clone();
        self.close_panels(cx);
        if url.is_empty() {
            self.show_start(cx, true);
            self.ui.text_input(cx, ids!(omnibox)).set_text(cx, "");
        } else {
            self.show_start(cx, false);
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
            self.ui.label(cx, id).set_text(cx, &text);
        }
    }

    fn refresh_settings(&self, cx: &mut Cx) {
        self.ui
            .label(cx, ids!(theme_value))
            .set_text(cx, THEMES[self.settings.theme as usize]);
        self.ui
            .label(cx, ids!(accent_value))
            .set_text(cx, ACCENTS[self.settings.accent as usize]);
        self.ui
            .label(cx, ids!(rail_value))
            .set_text(cx, &format!("{:.0} dp", RAIL_WIDTHS[self.settings.rail as usize]));
        self.ui
            .label(cx, ids!(labels_value))
            .set_text(cx, if self.settings.labels { "On" } else { "Off" });
        self.ui
            .label(cx, ids!(engine_value))
            .set_text(cx, ENGINES[self.settings.engine as usize].0);
    }

    fn apply_appearance(&mut self, cx: &mut Cx) {
        match self.settings.theme {
            0 => script_eval!(cx, {mod.theme = mod.themes.dark true}),
            1 => script_eval!(cx, {mod.theme = mod.themes.light true}),
            _ => script_eval!(cx, {mod.theme = mod.themes.skeleton true}),
        }
        match self.settings.accent {
            0 => script_eval!(cx, {mod.theme.color_focus = #9FC5E8FF true}),
            1 => script_eval!(cx, {mod.theme.color_focus = #C89B78FF true}),
            _ => script_eval!(cx, {mod.theme.color_focus = #8FB69AFF true}),
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
            self.close_panels(cx);
            self.ui.widget(cx, ids!(settings_panel)).set_visible(cx, true);
            self.apply_appearance(cx);
        }
        if self.ui.button(cx, ids!(rail_history)).clicked(actions) {
            self.close_panels(cx);
            self.refresh_history(cx);
            self.ui.widget(cx, ids!(history_panel)).set_visible(cx, true);
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
                WebViewAction::Title(title) => {
                    if !title.is_empty() {
                        self.ui.label(cx, ids!(tagline)).set_text(cx, &title);
                    }
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
            self.close_panels(cx);
            self.show_start(cx, true);
        }
        if let Event::BackPressed = event {
            if event.back_pressed() {
                if self.web(cx).state().can_go_back {
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
