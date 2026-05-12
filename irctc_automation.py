#!/usr/bin/env python3
"""IRCTC booking helper with GUI and CLI fallback.

This script modernizes the original automation by using:
- Selenium 4 locator patterns and explicit waits
- WebDriver manager fallback
- Better error handling and logging
- Optional CLI mode when Tkinter cannot start

Note:
IRCTC changes UI/flows often. Locator updates may still be needed over time.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from tkinter import Button, Entry, Frame, Label, LEFT, Tk, TclError
except Exception:  # pragma: no cover - environment dependent
    Button = Entry = Frame = Label = LEFT = Tk = None
    TclError = RuntimeError

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
except Exception:  # pragma: no cover - optional dependency
    ChromeDriverManager = None


FieldLocators = Sequence[Tuple[str, str]]

DEFAULT_URL = "https://www.irctc.co.in/nget/train-search"
LOGIN_WAIT_SECONDS = 90
DEFAULT_CAPTCHA_WAIT_SECONDS = 25

# Top-level journey fields shown in GUI.
BASE_FIELDS = [
    "UserID",
    "Password",
    "TrainNo",
    "FromStation",
    "ToStation",
    "Date",  # expected format: DD-MM-YYYY
    "Class",
    "Quota",
    "MobileNo",
]


@dataclass
class Passenger:
    name: str
    age: str
    gender: str


class BookingAutomation:
    def __init__(
        self,
        values: Dict[str, str],
        passengers: List[Passenger],
        headless: bool = False,
        captcha_wait_seconds: int = DEFAULT_CAPTCHA_WAIT_SECONDS,
        driver_path: Optional[str] = None,
    ) -> None:
        self.values = values
        self.passengers = [p for p in passengers if p.name.strip()]
        self.headless = headless
        self.captcha_wait_seconds = captcha_wait_seconds
        self.driver_path = driver_path
        self.browser: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")

        if self.driver_path:
            service = Service(self.driver_path)
            return webdriver.Chrome(service=service, options=options)

        # Try webdriver-manager first, fallback to Selenium Manager / PATH.
        if ChromeDriverManager is not None:
            try:
                service = Service(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=options)
            except Exception:
                pass

        return webdriver.Chrome(options=options)

    def _wait_clickable(self, locators: FieldLocators, timeout: int = 20):
        assert self.wait is not None
        last_error: Optional[Exception] = None
        for by, locator in locators:
            try:
                return WebDriverWait(self.browser, timeout).until(
                    EC.element_to_be_clickable((by, locator))
                )
            except Exception as err:
                last_error = err
        raise TimeoutException(f"No clickable element found for locators: {locators}") from last_error

    def _wait_present(self, locators: FieldLocators, timeout: int = 20):
        assert self.wait is not None
        last_error: Optional[Exception] = None
        for by, locator in locators:
            try:
                return WebDriverWait(self.browser, timeout).until(
                    EC.presence_of_element_located((by, locator))
                )
            except Exception as err:
                last_error = err
        raise TimeoutException(f"No element found for locators: {locators}") from last_error

    def _type(self, locators: FieldLocators, value: str, clear_first: bool = True) -> None:
        if value is None:
            return
        element = self._wait_present(locators)
        if clear_first:
            element.clear()
        element.send_keys(value)

    def _click(self, locators: FieldLocators) -> None:
        self._wait_clickable(locators).click()

    def _pause_for_user(self, message: str, seconds: int) -> None:
        print(message)
        for i in range(seconds, 0, -1):
            print(f"Continuing in {i:02d}s...", end="\r", flush=True)
            time.sleep(1)
        print(" " * 40, end="\r")

    def run_health_check(self) -> None:
        self.browser = self._build_driver()
        try:
            self.browser.get(DEFAULT_URL)
            print("Health check passed: IRCTC page opened.")
        finally:
            self.browser.quit()

    def run_booking(self) -> None:
        if not self.passengers:
            raise ValueError("At least one passenger name is required.")

        self.browser = self._build_driver()
        self.wait = WebDriverWait(self.browser, LOGIN_WAIT_SECONDS)

        try:
            self.browser.get(DEFAULT_URL)

            # Open login modal.
            self._click(
                [
                    (By.XPATH, "//a[contains(normalize-space(), 'LOGIN') or contains(normalize-space(), 'Login') ]"),
                    (By.XPATH, "//button[contains(normalize-space(), 'LOGIN') or contains(normalize-space(), 'Login') ]"),
                ]
            )

            # Fill credentials.
            self._type(
                [
                    (By.ID, "userId"),
                    (By.ID, "usernameId"),
                    (By.XPATH, "//input[@formcontrolname='userid']"),
                    (By.XPATH, "//input[contains(@placeholder, 'User')]"),
                ],
                self.values.get("UserID", ""),
            )
            self._type(
                [
                    (By.ID, "pwd"),
                    (By.NAME, "j_password"),
                    (By.XPATH, "//input[@type='password']"),
                ],
                self.values.get("Password", ""),
            )

            self._pause_for_user(
                "Please solve captcha/OTP manually in the browser window.",
                self.captcha_wait_seconds,
            )

            self._click(
                [
                    (By.XPATH, "//button[contains(normalize-space(), 'SIGN IN') or contains(normalize-space(), 'Login')]"),
                    (By.ID, "loginbutton"),
                ]
            )

            # Journey search section.
            self._type(
                [
                    (By.ID, "origin"),
                    (By.XPATH, "//input[@aria-controls='pr_id_1_list']"),
                    (By.XPATH, "//input[contains(@placeholder, 'From')]"),
                ],
                self.values.get("FromStation", ""),
            )
            self._type(
                [
                    (By.ID, "destination"),
                    (By.XPATH, "//input[@aria-controls='pr_id_2_list']"),
                    (By.XPATH, "//input[contains(@placeholder, 'To')]"),
                ],
                self.values.get("ToStation", ""),
            )
            self._type(
                [
                    (By.XPATH, "//input[contains(@placeholder, 'Journey Date')]"),
                    (By.XPATH, "//p-calendar//input"),
                ],
                self.values.get("Date", ""),
            )

            # Optional selectors - may vary by release.
            if self.values.get("Class"):
                try:
                    self._click([(By.XPATH, "//p-dropdown[@formcontrolname='journeyClass']//div[contains(@class, 'dropdown')]" )])
                    self._click([(By.XPATH, f"//li[@aria-label='{self.values['Class']}']")])
                except Exception:
                    pass

            if self.values.get("Quota"):
                try:
                    self._click([(By.XPATH, "//p-dropdown[@formcontrolname='journeyQuota']//div[contains(@class, 'dropdown')]" )])
                    self._click([(By.XPATH, f"//li[@aria-label='{self.values['Quota']}']")])
                except Exception:
                    pass

            self._click(
                [
                    (By.XPATH, "//button[contains(normalize-space(), 'Search') or contains(normalize-space(), 'Find Trains')]"),
                    (By.XPATH, "//button[contains(@class, 'search_btn')]"),
                ]
            )

            print("Search flow completed. Passenger and payment steps may need selector updates per IRCTC UI release.")
            print("Next step: verify passenger and payment locators with a live booking session.")

        finally:
            if self.browser is not None:
                self.browser.quit()


class BookingGui(Frame):
    def __init__(self, master):
        super().__init__(master)
        self.entries: Dict[str, Entry] = {}
        self.passenger_entries: List[Dict[str, Entry]] = []

    def build(self) -> None:
        row = 0
        for field in BASE_FIELDS:
            Label(self, text=field).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            show = "*" if field == "Password" else None
            entry = Entry(self, show=show, width=32)
            entry.grid(row=row, column=1, padx=4, pady=2)
            self.entries[field] = entry
            row += 1

        Label(self, text="CaptchaWaitSec").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        captcha_entry = Entry(self, width=32)
        captcha_entry.insert(0, str(DEFAULT_CAPTCHA_WAIT_SECONDS))
        captcha_entry.grid(row=row, column=1, padx=4, pady=2)
        self.entries["CaptchaWaitSec"] = captcha_entry
        row += 1

        Label(self, text="Passengers (Name / Age / Gender)").grid(row=row, column=0, columnspan=3, sticky="w", padx=4, pady=8)
        row += 1

        for i in range(4):
            Label(self, text=f"P{i + 1}").grid(row=row, column=0, sticky="w", padx=4)
            name_entry = Entry(self, width=18)
            age_entry = Entry(self, width=8)
            gender_entry = Entry(self, width=10)
            name_entry.grid(row=row, column=1, padx=2, pady=2)
            age_entry.grid(row=row, column=2, padx=2, pady=2)
            gender_entry.grid(row=row, column=3, padx=2, pady=2)
            self.passenger_entries.append({"name": name_entry, "age": age_entry, "gender": gender_entry})
            row += 1

        Button(self, text="Book Tatkal Ticket", command=self.on_submit).grid(row=row, column=1, pady=10)

    def on_submit(self) -> None:
        values = {k: e.get().strip() for k, e in self.entries.items()}
        passengers = [
            Passenger(
                name=p["name"].get().strip(),
                age=p["age"].get().strip(),
                gender=p["gender"].get().strip(),
            )
            for p in self.passenger_entries
        ]

        try:
            captcha_wait = int(values.get("CaptchaWaitSec", DEFAULT_CAPTCHA_WAIT_SECONDS) or DEFAULT_CAPTCHA_WAIT_SECONDS)
        except ValueError:
            captcha_wait = DEFAULT_CAPTCHA_WAIT_SECONDS

        runner = BookingAutomation(values=values, passengers=passengers, captcha_wait_seconds=captcha_wait)
        try:
            runner.run_booking()
            print("Automation run finished.")
        except Exception as exc:
            print(f"Automation failed: {exc}")


def _load_config(config_path: Path) -> Tuple[Dict[str, str], List[Passenger], int]:
    data = json.loads(config_path.read_text(encoding="utf-8"))

    values = {field: str(data.get(field, "")).strip() for field in BASE_FIELDS}
    captcha_wait = int(data.get("CaptchaWaitSec", DEFAULT_CAPTCHA_WAIT_SECONDS))

    passengers: List[Passenger] = []
    for item in data.get("passengers", []):
        passengers.append(
            Passenger(
                name=str(item.get("name", "")).strip(),
                age=str(item.get("age", "")).strip(),
                gender=str(item.get("gender", "")).strip(),
            )
        )

    return values, passengers, captcha_wait


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IRCTC booking automation helper")
    parser.add_argument("--no-gui", action="store_true", help="Run without Tkinter GUI")
    parser.add_argument("--config", type=Path, help="Path to JSON config for --no-gui mode")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--health-check", action="store_true", help="Only open IRCTC homepage and exit")
    parser.add_argument("--driver-path", type=str, help="Optional local chromedriver path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.health_check:
        runner = BookingAutomation(values={}, passengers=[], headless=args.headless, driver_path=args.driver_path)
        runner.run_health_check()
        return 0

    if args.no_gui:
        if not args.config:
            raise ValueError("--config is required when using --no-gui")
        values, passengers, captcha_wait = _load_config(args.config)
        runner = BookingAutomation(
            values=values,
            passengers=passengers,
            headless=args.headless,
            captcha_wait_seconds=captcha_wait,
            driver_path=args.driver_path,
        )
        runner.run_booking()
        return 0

    if Tk is None:
        raise RuntimeError("Tkinter is not available in this Python runtime. Use --no-gui mode.")

    try:
        root = Tk()
    except TclError as err:
        raise RuntimeError(
            "Tkinter GUI could not start in this runtime. Use a system Python with Tk support "
            "or run in --no-gui mode with a JSON config."
        ) from err

    root.title("IRCTC Automation")
    app = BookingGui(root)
    app.build()
    app.pack(side=LEFT)
    root.mainloop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
