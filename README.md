# IRCTC-Automation
# IRCTC Automation (Upgraded)

This project automates parts of IRCTC booking using Python + Selenium.

The script has been upgraded to:
- Use Selenium 4 style APIs and explicit waits
- Use modern ChromeDriver startup (with fallback)
- Support `--health-check` mode
- Support `--no-gui` mode with JSON input
- Show clear errors when Tkinter GUI is unavailable

## Important Note

IRCTC changes UI flows frequently (login, captcha, OTP, search widgets, payment flow).  
You should expect occasional selector updates.

Captcha/OTP must still be completed manually.

## Prerequisites

- Python 3.10+
- Google Chrome installed
- Packages:

```bash
pip install selenium webdriver-manager
```

## Quick Health Check

Verifies browser + driver + IRCTC page launch:

```bash
python irctc_automation.py --health-check --headless
```

## GUI Mode

```bash
python irctc_automation.py
```

If your Python runtime does not include Tkinter/Tcl, use `--no-gui` mode below.

## Non-GUI Mode

1. Copy and edit `config.example.json` (for example `config.json`).
2. Fill your own values.
3. Run:

```bash
python irctc_automation.py --no-gui --config config.json
```

Optional:
- `--headless` to run without visible browser
- `--driver-path <path-to-chromedriver>` if you want a fixed driver

## Config Format

See `config.example.json`.

## Known Limitations

- Passenger and payment sections on IRCTC can require selector tuning after site updates.
- During Tatkal windows, timing/network delays and anti-bot checks can still break flows.
- Keep captcha/OTP and final payment confirmation manual for reliability and safety.
