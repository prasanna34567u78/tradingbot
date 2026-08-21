import time
import subprocess
import MetaTrader5 as mt5

def enable_mt5_autotrading():
    """
    Automates pressing Ctrl+E in MetaTrader 5 to turn on AlgoTrading.
    """
    print("Checking MT5 Terminal AlgoTrading status...")
    if not mt5.initialize(r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        print("Failed to initialize MT5.")
        return False
        
    info = mt5.terminal_info()
    if info and info.trade_allowed:
        print("[OK] MT5 AlgoTrading is ALREADY ENABLED!")
        return True
        
    print("[INFO] AlgoTrading is currently DISABLED. Sending Ctrl+E shortcut to MT5...")
    ps_script = """
    $wshell = New-Object -ComObject wscript.shell;
    $mt5 = Get-Process terminal64 -ErrorAction SilentlyContinue;
    if ($mt5) {
        $wshell.AppActivate($mt5.Id);
        Start-Sleep -Milliseconds 500;
        $wshell.SendKeys("^{e}");
        Write-Host "Sent Ctrl+E shortcut to MT5 window";
    } else {
        Write-Host "MetaTrader 5 process not running";
    }
    """
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout.strip())
    
    time.sleep(1)
    info_after = mt5.terminal_info()
    if info_after and info_after.trade_allowed:
        print("[SUCCESS] MT5 AlgoTrading is now ENABLED!")
        return True
    else:
        print("[NOTE] If MT5 options block AlgoTrading, open MT5 -> Ctrl+O -> Expert Advisors -> Check 'Allow Algo Trading'.")
        return False

if __name__ == "__main__":
    enable_mt5_autotrading()
