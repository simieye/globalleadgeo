// 全球鹰 GEO 全球AI推荐系统 · macOS 原生窗口壳
// 用 WKWebView 承载本地服务界面：自带独立窗口、Dock 图标与菜单栏，
// 并负责拉起 / 关闭本地 Python 服务（127.0.0.1:8787）。
import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {

    private let port: String = ProcessInfo.processInfo.environment["GEO_PORT"] ?? "8787"
    private var serverProcess: Process?
    private var window: NSWindow!
    private var webView: WKWebView!
    private var statusLabel: NSTextField!
    private var spinner: NSProgressIndicator!
    private var booted = false

    private var resourceDir: String { Bundle.main.resourcePath ?? "" }
    private var baseURL: String { "http://127.0.0.1:\(port)" }
    private var logPath: String {
        let dir = NSSearchPathForDirectoriesInDomains(.applicationSupportDirectory, .userDomainMask, true).first ?? NSHomeDirectory()
        return dir + "/GlobalEagleGEO/server.log"
    }

    // MARK: - 生命周期

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        buildMenu()
        buildWindow()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in self?.boot() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        serverProcess?.terminate()
    }

    // MARK: - 启动流程

    private func boot() {
        if healthy() {
            loadConsole()
            return
        }
        setStatus("首次运行：正在准备 Python 运行环境（约 1–3 分钟）…")
        startServer()
        if waitUntilHealthy(seconds: 240) {
            loadConsole()
        } else {
            showFailure()
        }
    }

    private func startServer() {
        let script = resourceDir + "/server.sh"
        guard FileManager.default.isExecutableFile(atPath: script) else { return }
        let fm = FileManager.default
        try? fm.createDirectory(atPath: (logPath as NSString).deletingLastPathComponent,
                                withIntermediateDirectories: true)
        if !fm.fileExists(atPath: logPath) { fm.createFile(atPath: logPath, contents: nil) }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = [script]
        var env = ProcessInfo.processInfo.environment
        env["GEO_PORT"] = port
        process.environment = env
        if let handle = FileHandle(forWritingAtPath: logPath) {
            handle.seekToEndOfFile()
            process.standardOutput = handle
            process.standardError = handle
        }
        do {
            try process.run()
            serverProcess = process
        } catch {
            NSLog("[GlobalEagleGEO] 服务启动失败: \(error)")
        }
    }

    private func healthy() -> Bool {
        guard let url = URL(string: baseURL + "/api/health") else { return false }
        let semaphore = DispatchSemaphore(value: 0)
        var ok = false
        let task = URLSession.shared.dataTask(with: url) { _, response, error in
            if error == nil, let http = response as? HTTPURLResponse, http.statusCode == 200 { ok = true }
            semaphore.signal()
        }
        task.resume()
        _ = semaphore.wait(timeout: .now() + 2)
        return ok
    }

    private func waitUntilHealthy(seconds: Int) -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(seconds))
        while Date() < deadline {
            if healthy() { return true }
            Thread.sleep(forTimeInterval: 0.5)
        }
        return healthy()
    }

    private func loadConsole() {
        guard !booted, let url = URL(string: baseURL) else { return }
        booted = true
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.spinner.stopAnimation(nil)
            self.statusLabel.isHidden = true
            self.webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
        }
    }

    private func setStatus(_ text: String) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.statusLabel.stringValue = text
            self.statusLabel.isHidden = false
            self.spinner.startAnimation(nil)
        }
    }

    private func showFailure() {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.spinner.stopAnimation(nil)
            self.statusLabel.stringValue = "服务启动失败，请查看日志：\n" + self.logPath
            let alert = NSAlert()
            alert.alertStyle = .critical
            alert.messageText = "服务启动失败"
            alert.informativeText = "请查看日志：\(self.logPath)"
            alert.addButton(withTitle: "打开日志")
            alert.addButton(withTitle: "重试")
            alert.addButton(withTitle: "退出")
            let response = alert.runModal()
            switch response {
            case .alertFirstButtonReturn:
                NSWorkspace.shared.open(URL(fileURLWithPath: self.logPath))
                NSApp.terminate(nil)
            case .alertSecondButtonReturn:
                self.booted = false
                DispatchQueue.global(qos: .userInitiated).async { [weak self] in self?.boot() }
            default:
                NSApp.terminate(nil)
            }
        }
    }

    // MARK: - 界面

    private func buildWindow() {
        let frame = NSRect(x: 0, y: 0, width: 1440, height: 900)
        let window = NSWindow(contentRect: frame,
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                              backing: .buffered,
                              defer: false)
        window.title = "全球鹰 GEO · 全球AI推荐系统"
        window.titlebarAppearsTransparent = false
        window.minSize = NSSize(width: 1024, height: 640)
        window.center()
        window.tabbingMode = .disallowed
        window.isReleasedWhenClosed = false
        self.window = window

        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        let webView = WKWebView(frame: frame, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.autoresizingMask = [.width, .height]
        self.webView = webView

        let container = NSView(frame: frame)
        container.wantsLayer = true
        container.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        container.addSubview(webView)

        let spinner = NSProgressIndicator(frame: NSRect(x: 0, y: 0, width: 28, height: 28))
        spinner.style = .spinning
        spinner.isDisplayedWhenStopped = false
        spinner.translatesAutoresizingMaskIntoConstraints = false
        self.spinner = spinner

        let label = NSTextField(labelWithString: "正在启动本地服务…")
        label.font = NSFont.systemFont(ofSize: 14)
        label.alignment = .center
        label.textColor = .secondaryLabelColor
        label.translatesAutoresizingMaskIntoConstraints = false
        self.statusLabel = label

        container.addSubview(spinner)
        container.addSubview(label)

        NSLayoutConstraint.activate([
            spinner.centerXAnchor.constraint(equalTo: container.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: container.centerYAnchor, constant: 18),
            label.centerXAnchor.constraint(equalTo: container.centerXAnchor),
            label.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 12),
            label.leadingAnchor.constraint(greaterThanOrEqualTo: container.leadingAnchor, constant: 24),
            label.trailingAnchor.constraint(lessThanOrEqualTo: container.trailingAnchor, constant: -24)
        ])

        window.contentView = container
        window.makeKeyAndOrderFront(nil)
    }

    private func buildMenu() {
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(title: "关于 全球鹰 GEO", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        let quit = NSMenuItem(title: "退出 全球鹰 GEO", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenu.addItem(quit)
        appItem.submenu = appMenu
        mainMenu.addItem(appItem)

        let editItem = NSMenuItem()
        let editMenu = NSMenu(title: "编辑")
        editMenu.addItem(NSMenuItem(title: "撤销", action: Selector(("undo:")), keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "重做", action: Selector(("redo:")), keyEquivalent: "Z"))
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(NSMenuItem(title: "剪切", action: #selector(NSText.cut(_:)), keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "拷贝", action: #selector(NSText.copy(_:)), keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "粘贴", action: #selector(NSText.paste(_:)), keyEquivalent: "v"))
        editMenu.addItem(NSMenuItem(title: "全选", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"))
        editItem.submenu = editMenu
        mainMenu.addItem(editItem)

        let viewItem = NSMenuItem()
        let viewMenu = NSMenu(title: "显示")
        viewMenu.addItem(NSMenuItem(title: "重新加载", action: #selector(reloadPage(_:)), keyEquivalent: "r"))
        viewMenu.addItem(NSMenuItem(title: "在浏览器中打开", action: #selector(openInBrowser(_:)), keyEquivalent: "b"))
        viewItem.submenu = viewMenu
        mainMenu.addItem(viewItem)

        NSApp.mainMenu = mainMenu
    }

    @objc private func reloadPage(_ sender: Any?) {
        webView.reload()
    }

    @objc private func openInBrowser(_ sender: Any?) {
        NSWorkspace.shared.open(URL(string: baseURL)!)
    }

    // MARK: - WKWebView 代理

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }
        let isLocal = url.host == "127.0.0.1" || url.host == "localhost"
        if !isLocal || navigationAction.targetFrame == nil {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        setStatus("无法连接本地服务（\(error.localizedDescription)），正在重试…")
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            if self.healthy() { self.loadConsole() }
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
