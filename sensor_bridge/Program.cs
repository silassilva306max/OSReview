// OSReview - companion hardware telemetry bridge. Third-party: LibreHardwareMonitorLib 0.9.6.
// (c) LibreHardwareMonitor and contributors, licensed MPL 2.0.
// https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
// Emits only JSON Lines to STDOUT; diagnostics on STDERR; read-only sensors.
using LibreHardwareMonitor.Hardware;
using System.Text.Json;

bool stream = args.Contains("--stream", StringComparer.OrdinalIgnoreCase);
int intervalMs = 2500;
var computer = new Computer {
    IsCpuEnabled=true, IsGpuEnabled=true, IsMemoryEnabled=true,
    IsMotherboardEnabled=true, IsStorageEnabled=true,
    IsControllerEnabled=true, IsPsuEnabled=true, IsPowerMonitorEnabled=true,
    IsBatteryEnabled=true
};

// Important: initialize all hardware groups BEFORE Open(). With Intel integrated
// graphics, the group needs the enabled Intel CPU group at initialization.
try {
    computer.Open();
    do {
        var rows = new List<object>();
        var warnings = new List<string>();
        var absent = new List<object>();
        var catalog = new List<object>();
        int devices = 0;
        foreach (var hw in computer.Hardware) {
            devices++;
            Visit(hw, hw.Name, rows, warnings, absent, catalog);
        }
        var packet = new {
            ok = rows.Count > 0,
            sensors = rows,
            devices = devices,
            warnings = warnings.Take(30).ToArray(),
            hardware = catalog.Take(100).ToArray(),
            unavailable = absent.Take(240).ToArray(),
            missingCount = absent.Count,
            timestamp_utc = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            status = rows.Count > 0 ? "sensores coletados" :
                "nenhum sensor exposto: verificar permissões, driver e compatibilidade"
        };
        Console.Out.WriteLine(JsonSerializer.Serialize(packet));
        Console.Out.Flush();
        if (!stream) break;
        Thread.Sleep(intervalMs);
    } while (true);
} catch (Exception e) {
    Console.Error.WriteLine(e.GetType().Name + ": " + e.Message);
    Console.Out.WriteLine(JsonSerializer.Serialize(new { ok=false, sensors=Array.Empty<object>(),
        devices=0, warnings=new[]{e.GetType().Name+": "+e.Message},
        status="falha no motor de sensores" }));
    Console.Out.Flush();
    Environment.ExitCode = 2;
} finally { computer.Close(); }

static void Visit(IHardware hw, string parent, List<object> rows, List<string> warnings,
    List<object> absent, List<object> catalog) {
    try {
        hw.Update();
        catalog.Add(new { Hardware=hw.Name, Type=hw.HardwareType.ToString(),
            SensorCount=hw.Sensors.Count(), SubdeviceCount=hw.SubHardware.Count() });
        foreach (var sensor in hw.Sensors) {
            if (sensor.Value is not float value || !float.IsFinite(value)) {
                absent.Add(new { Hardware=hw.Name, Type=hw.HardwareType.ToString(),
                    Sensor=sensor.Name, SensorType=sensor.SensorType.ToString(),
                    Reason="sem valor reportado pela biblioteca" });
                continue;
            }
            rows.Add(new {
                Name=sensor.Name, SensorType=sensor.SensorType.ToString(), Value=value,
                Identifier=sensor.Identifier.ToString(), Parent=parent,
                Device=hw.Name, HardwareType=hw.HardwareType.ToString()
            });
        }
        foreach (var sub in hw.SubHardware) Visit(sub, parent, rows, warnings, absent, catalog);
    } catch (Exception e) {
        warnings.Add(hw.Name + ": " + e.GetType().Name + ": " + e.Message);
    }
}
