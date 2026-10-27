// OSReview native macOS installer (AppKit). No Terminal, shell execution or Python required.
// Per-user install in a user-writable folder. All options opt-in.
import AppKit
import Foundation

@MainActor
final class OSReviewInstaller: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        startInstallation()
        NSApp.terminate(nil)
    }

    private func alert(title: String, text: String, style: NSAlert.Style = .informational) {
        let dialog = NSAlert()
        dialog.messageText = title
        dialog.informativeText = text
        dialog.alertStyle = style
        dialog.addButton(withTitle: "OK")
        dialog.runModal()
    }

    private func startInstallation() {
        let files = FileManager.default
        let appSource = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/OSReview.app", isDirectory: true)
        guard files.fileExists(atPath: appSource.path) else {
            alert(title: "Pacote incompleto", text: "OSReview.app não está incluído no instalador. Não foi feita nenhuma alteração.", style: .critical)
            return
        }
        let home = files.homeDirectoryForCurrentUser
        let defaultFolder = home.appendingPathComponent("Applications", isDirectory: true)
        do {
            try files.createDirectory(at: defaultFolder, withIntermediateDirectories: true)
        } catch {
            alert(title: "Pasta padrão inacessível", text: error.localizedDescription, style: .critical)
            return
        }

        let folder = NSOpenPanel()
        folder.title = "OSReview — escolher local da instalação"
        folder.message = "Escolha uma pasta onde seu usuário tenha permissão de gravação."
        folder.prompt = "Usar esta pasta"
        folder.directoryURL = defaultFolder
        folder.canChooseDirectories = true
        folder.canChooseFiles = false
        folder.canCreateDirectories = true
        folder.allowsMultipleSelection = false
        guard folder.runModal() == .OK, let parent = folder.url else { return }
        let target = parent.appendingPathComponent("OSReview.app", isDirectory: true)

        let desktop = NSButton(checkboxWithTitle: "Criar atalho na Mesa (Área de Trabalho)", target: nil, action: nil)
        desktop.state = .off
        let login = NSButton(checkboxWithTitle: "Iniciar OSReview ao entrar no macOS", target: nil, action: nil)
        login.state = .off
        let launch = NSButton(checkboxWithTitle: "Abrir OSReview após a instalação", target: nil, action: nil)
        launch.state = .on
        let options = NSStackView(views: [desktop, login, launch])
        options.orientation = .vertical
        options.alignment = .leading
        options.spacing = 8
        options.translatesAutoresizingMaskIntoConstraints = false
        let accessory = NSView(frame: NSRect(x: 0, y: 0, width: 390, height: 94))
        accessory.addSubview(options)
        NSLayoutConstraint.activate([
            options.leadingAnchor.constraint(equalTo: accessory.leadingAnchor),
            options.topAnchor.constraint(equalTo: accessory.topAnchor),
            options.trailingAnchor.constraint(lessThanOrEqualTo: accessory.trailingAnchor),
            options.bottomAnchor.constraint(lessThanOrEqualTo: accessory.bottomAnchor)
        ])

        let confirm = NSAlert()
        confirm.messageText = "Instalar OSReview 0.9.1 RC2"
        confirm.informativeText = "Destino: \(target.path)\n\nO aplicativo já inclui suas bibliotecas. Não instalará Python nem .NET no Mac."
        confirm.alertStyle = .informational
        confirm.accessoryView = accessory
        confirm.addButton(withTitle: "Instalar")
        confirm.addButton(withTitle: "Cancelar")
        guard confirm.runModal() == .alertFirstButtonReturn else { return }

        // Never remove an existing application until its replacement is available.
        let temp = parent.appendingPathComponent(".OSReview-install-\(UUID().uuidString).app", isDirectory: true)
        let backup = parent.appendingPathComponent(".OSReview-backup-\(UUID().uuidString).app", isDirectory: true)
        var oldWasMoved = false
        do {
            try files.copyItem(at: appSource, to: temp)
            if files.fileExists(atPath: target.path) {
                try files.moveItem(at: target, to: backup)
                oldWasMoved = true
            }
            do { try files.moveItem(at: temp, to: target) }
            catch {
                if oldWasMoved { try? files.moveItem(at: backup, to: target) }
                throw error
            }
            if oldWasMoved { try? files.removeItem(at: backup) }
        } catch {
            try? files.removeItem(at: temp)
            alert(title: "Não foi possível instalar", text: "A pasta selecionada pode não permitir gravação.\n\n\(error.localizedDescription)", style: .critical)
            return
        }

        var notes: [String] = ["OSReview foi instalado em: \(target.path)"]
        if desktop.state == .on {
            let shortcut = home.appendingPathComponent("Desktop/OSReview.app")
            if files.fileExists(atPath: shortcut.path) || (try? files.destinationOfSymbolicLink(atPath: shortcut.path)) != nil {
                notes.append("Atalho já existente na Mesa: não foi modificado.")
            } else {
                do { try files.createSymbolicLink(at: shortcut, withDestinationURL: target) }
                catch { notes.append("Atalho não criado: \(error.localizedDescription)") }
            }
        }
        if login.state == .on {
            let agents = home.appendingPathComponent("Library/LaunchAgents", isDirectory: true)
            let plist = agents.appendingPathComponent("com.osreview.diagnostics.login.plist")
            let executable = target.appendingPathComponent("Contents/MacOS/OSReview").path
            let entry: [String: Any] = ["Label":"com.osreview.diagnostics.login", "ProgramArguments":[executable], "RunAtLoad":true, "KeepAlive":false]
            do {
                try files.createDirectory(at: agents, withIntermediateDirectories: true)
                let data = try PropertyListSerialization.data(fromPropertyList: entry, format: .xml, options: 0)
                try data.write(to: plist, options: .atomic)
                notes.append("Início de sessão configurado para o próximo login do usuário.")
            } catch { notes.append("Não foi possível configurar início automático: \(error.localizedDescription)") }
        }
        if launch.state == .on {
            if !NSWorkspace.shared.open(target) { notes.append("Abra OSReview.app pelo Finder para iniciar.") }
        }
        alert(title: "Instalação concluída", text: notes.joined(separator: "\n\n"))
    }
}

@main
struct OSReviewInstallerMain {
    @MainActor
    static func main() {
        let application = NSApplication.shared
        let delegate = OSReviewInstaller()
        application.delegate = delegate
        application.run()
    }
}
