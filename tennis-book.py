#!/usr/bin/env python3
"""
Tennis Book Application - Automated tennis court booking via PlayByPoint.
"""

import logging
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from playwright.sync_api import Playwright, sync_playwright

# Credentials - use environment variables for security
USER_NAME = os.getenv("PLAYBYPOINT_EMAIL", "")
USER_PWD = os.getenv("PLAYBYPOINT_PASSWORD", "")
BOOKED_DATE_FILE = os.getenv("BOOKED_DATE_FILE")
BOOKING_SLOTS_ENV = os.getenv("BOOKING_SLOTS", "")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY", "")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN", "")


# Global wait constants: base wait (seconds) plus up-to `WAIT_JITTER` seconds random
WAIT_BASE = 3.0
WAIT_JITTER = 2.0


def wait_random() -> None:
    """Sleep for `WAIT_BASE` seconds plus up to `WAIT_JITTER` seconds random delay.

    Use global constants so timing is consistent and configurable from one place.
    """
    time.sleep(WAIT_BASE + random.random() * WAIT_JITTER)  # nosec B311


# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s: %(message)s",
)


def send_pushover_message(user_key, api_token, message, title=None):
    """Send a notification to Pushover. Prints errors but does not raise.

    This helper is safe to call from exception handlers.
    """
    if not user_key or not api_token:
        logging.warning("Pushover credentials not set; skipping notification.")
        return

    url = "https://api.pushover.net/1/messages.json"

    payload = {
        "token": api_token,
        "user": user_key,
        "message": message,
    }

    if title:
        payload["title"] = title

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logging.info("Pushover: message sent successfully")
    except requests.exceptions.RequestException as e:
        logging.exception(f"Pushover: failed to send message: {e}")


def ensure_element(
    locator, description: str, max_retries: int = 3, base_delay: float = 1.0
):
    """Verify the given Playwright locator matches at least one element.

    Retries with exponential backoff if the element is not found.
    Logs an error and raises RuntimeError if all retries fail.
    Returns the locator for convenience.

    Args:
        locator: Playwright locator object
        description: Human-readable description of the element
        max_retries: Number of retries with exponential backoff (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
    """
    for attempt in range(max_retries):
        try:
            count = locator.count()
            if count > 0:
                return locator
        except Exception:
            if attempt == max_retries - 1:
                logging.error(
                    "Failed to query element after %d retries: %s",
                    max_retries,
                    description,
                )
                raise

        # Calculate exponential backoff with jitter
        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt) + random.random() * 0.1  # nosec B311
            logging.debug(
                "Element not found: %s, retrying in %.2fs (attempt %d/%d)",
                description,
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)

    logging.error("%s not found after %d retries.", description, max_retries)
    raise RuntimeError(f"{description} not found")


def _parse_date_iso(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        logging.warning("Could not parse saved date '%s' (expected YYYY-MM-DD)", s)
        return None


def parse_booking_slots(slots_str: str) -> list[tuple[str, list[str]]]:
    """Parse booking slots from environment variable format.

    Format: "day1_slot1_slot2:...,day2_slot1_slot2:..."
    Example: "Sun_8am_8:30am_9am,Tue_5pm_5:30pm"

    Args:
        slots_str: String containing booking slots configuration

    Returns:
        List of (day, time_slots_list) tuples. Empty list if slots_str is empty.
    """
    if not slots_str or not slots_str.strip():
        return []

    bookings = []
    for day_entry in slots_str.split(","):
        day_entry = day_entry.strip()
        if not day_entry:
            continue
        parts = day_entry.split("_")
        if len(parts) < 2:
            logging.warning(
                "Invalid booking slot format '%s' (expected day_slot1_slot2_...)",
                day_entry,
            )
            continue
        day = parts[0].strip()
        time_slots = [slot.strip() for slot in parts[1:]]
        bookings.append((day, time_slots))
    return bookings


def load_booked_slots() -> set[tuple[str, str]]:
    """Load booked slots from file pointed to by BOOKED_DATE_FILE env var.

    File format: one line per booked slot in format "day_time_slot"
    Example lines:
        Sun_8am
        Sun_8:30am
        Tue_5pm

    Returns a set of (day, time_slot) tuples. Empty set if not available.
    """
    path = BOOKED_DATE_FILE
    if not path:
        return set()
    p = Path(path)
    if not p.exists():
        return set()
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        logging.warning("Failed to read booked-date file: %s", path)
        return set()

    booked = set()
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Split from right to handle times like "5:30pm"
        parts = line.rsplit("_", 1)
        if len(parts) == 2:
            day, time_slot = parts
            booked.add((day.strip(), time_slot.strip()))
    return booked


def save_booked_slot(day: str, time_slot: str) -> None:
    """Save a booked slot to the file.

    Args:
        day: Day of week (e.g., 'Sun', 'Tue')
        time_slot: Time slot (e.g., '8am', '5:30pm')
    """
    path = BOOKED_DATE_FILE
    if not path:
        return
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Load existing booked slots
        booked = load_booked_slots()
        # Add the new slot
        booked.add((day, time_slot))
        # Write all slots back
        lines = [f"{day}_{time_slot}" for day, time_slot in sorted(booked)]
        p.write_text("\n".join(lines), encoding="utf-8")
        logging.info("Wrote booked slot %s_%s to %s", day, time_slot, path)
    except Exception:
        logging.exception("Failed to write booked-date file: %s", path)


def next_date_for_day(day_str: str, reference: date | None = None) -> date:
    """Return the next date (including today) matching the weekday name/abbrev.

    day_str may be three-letter abbrev like 'Sat' or full name 'Saturday'.
    Searches up to 6 days ahead.
    """
    if reference is None:
        reference = date.today()
    name = day_str.strip()
    key = name[:3].capitalize()
    abb_to_wday = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    target = abb_to_wday.get(key)
    if target is None:
        return reference
    for i in range(0, 7):
        cand = reference + timedelta(days=i)
        if cand.weekday() == target:
            return cand
    return reference


def login(page, username: str, password: str) -> None:
    """Log in to PlayByPoint.

    Args:
        page: Playwright page object
        username: Email address for login
        password: Password for login
    """
    page.goto("https://app.playbypoint.com/users/sign_in")
    email = page.get_by_role("textbox", name="Email")
    ensure_element(email, "Email textbox")
    email.click()
    email.fill(username)
    email.press("Tab")
    pwd = page.get_by_role("textbox", name="Password")
    ensure_element(pwd, "Password textbox")
    pwd.fill(password)
    sign_btn = page.get_by_role("button", name="Sign in")
    ensure_element(sign_btn, "Sign in button")
    sign_btn.click()


def navigate_to_booking(page) -> None:
    """Navigate from login page to booking page."""
    time.sleep(1)  # Wait for login to complete and redirect
    link = page.get_by_role("link", name="Book Now")
    ensure_element(link, "Book Now link")
    link.click()


def select_sport(page, sport: str) -> None:
    """Select a sport type (e.g., 'Tennis', 'Free Play').

    Args:
        page: Playwright page object
        sport: Name of the sport to select
    """
    sport_btn = page.get_by_role("button", name=sport, exact=True)
    ensure_element(sport_btn, f"Sport button '{sport}'")
    sport_btn.click()


def explore_and_select_times(page, day: str, sport: str, end_times: list[str]) -> bool:
    """Explore a sport tab and select available time slots for a given day.

    Searches for a specific day and time ranges, selecting all matching available slots.

    Args:
        page: Playwright page object
        day: Day of week to search for (e.g., 'Sat', 'Mon')
        sport: Sport type tab to explore (e.g., 'Tennis', 'Free Play')
        end_times: List of (start_time, end_time) tuples to search for.
                    Example: [('8:30am', '9am'), ('9:30am', '10am')]

    Returns:
        bool: True if time slots were found and selected, False otherwise
    """
    # Click the sport tab
    select_sport(page, sport)

    # Click the day
    day_btn = page.get_by_role("button", name=day)
    try:
        ensure_element(day_btn, f"Day button '{day}'")
    except RuntimeError:
        logging.warning("Day button for %s not found.", day)
        return False
    day_btn.click()

    # Find and click available time slots matching the ranges
    buttons = []
    for end_time in end_times:
        # Look for buttons with time slot pattern (e.g., "-8:30am" or "-9am")
        # Unavailable buttons have class "red", so we skip those.
        end_button = page.locator(f'button:has-text("-{end_time}"):not(.red)')
        try:
            ensure_element(end_button, f"Time slot ending at {end_time}")
        except RuntimeError:
            logging.warning("No available time slot ending at %s found.", end_time)
            return False

        buttons.append(end_button)

    # We have found all requested time slots, click them
    for end_button in buttons:
        end_button.first.click()
    return True


def proceed_to_next(page) -> None:
    """Click the Next button to proceed."""
    btn = page.get_by_role("button", name="Next")
    ensure_element(btn, "Next button")
    btn.click()


def add_players(page, count: int = 1) -> None:
    """Add players to the booking.

    Args:
        page: Playwright page object
        count: Number of additional players to add
    """
    add_players_btn = page.get_by_role("button", name="Add Players")
    ensure_element(add_players_btn, "Add Players button")
    add_players_btn.click()
    for i in range(1, count + 1):
        add_btn = page.get_by_role("button", name="Add").nth(i)
        ensure_element(add_btn, f"Add button #{i}")
        add_btn.click()


def confirm_booking(page) -> None:
    """Confirm the booking."""
    book_btn = page.get_by_role("button", name="Book")
    ensure_element(book_btn, "Book button")
    book_btn.click()


def select_num_players(page, count: int) -> None:
    num_btn = page.get_by_role("button", name=str(count))
    ensure_element(num_btn, f"Number of players button {count}")
    num_btn.click()


def book_court(
    playwright: Playwright,
    username: str,
    password: str,
    day: str,
    time_slots: list[str],
    sports: list[str] | None = None,
    extra_player_count: int = 0,
) -> bool:
    """Complete flow: login, select sport/days, select times, and book.

    Args:
        playwright: Playwright instance
        username: Email for login
        password: Password for login
        day: Day to book (e.g., 'Sat')
        time_slots: End of time slots to book (e.g., ['8:30am', '9am'])
        sports: Sport types to try (default: ['Tennis', 'Free Play'])
        extra_player_count: Number of additional players to add (default: 0)

    Returns:
        bool: True if booking was successful, False if no slots available

    Raises:
        Exception: If an error occurs during the booking process
    """
    if sports is None:
        sports = ["Tennis", "Free Play"]
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Login flow
        login(page, username, password)
        navigate_to_booking(page)

        # Selection flow
        for sport in sports:
            if not explore_and_select_times(page, day, sport, time_slots):
                continue
            proceed_to_next(page)

            select_num_players(page, 1 + extra_player_count)

            # Player and confirmation flow
            if extra_player_count > 0:
                add_players(page, extra_player_count)
            proceed_to_next(page)
            confirm_booking(page)

            logging.info("Successfully booked court for %s at %s", day, time_slots)
            return True  # Exit after successful booking

        # No sports had available slots
        return False

    finally:
        context.close()
        browser.close()


def run_bookings() -> dict:
    """Run the booking process and return results.

    Raises:
        ValueError: If required environment variables are not set
        ValueError: If BOOKING_SLOTS is invalid or empty

    Returns:
        dict: Booking results with keys:
            - successful: list of (day, time_slots) tuples that were booked
            - unavailable: list of (day, time_slots) tuples with no available slots
            - skipped: list of (day, time_slots) tuples that were already booked
    """
    if not USER_NAME or not USER_PWD:
        raise ValueError(
            "PLAYBYPOINT_EMAIL and PLAYBYPOINT_PASSWORD environment variables required"
        )

    # Parse booking slots from environment variable
    bookings = parse_booking_slots(BOOKING_SLOTS_ENV)
    if not bookings:
        raise ValueError(
            "BOOKING_SLOTS environment variable not set or invalid format. "
            "Expected format: 'day1_slot1_slot2:...,day2_slot1_slot2:...'"
        )

    # Load already booked slots
    booked_slots = load_booked_slots()

    # Categorize bookings
    results = {"successful": [], "unavailable": [], "skipped": []}

    for day, time_slots in bookings:
        # Keep only time slots that haven't been booked yet
        pending_slots = [slot for slot in time_slots if (day, slot) not in booked_slots]
        if not pending_slots:
            results["skipped"].append((day, time_slots))
            logging.info("All slots for %s are already booked", day)
            continue

        # Try to book pending slots
        with sync_playwright() as playwright:
            success = book_court(
                playwright,
                username=USER_NAME,
                password=USER_PWD,
                day=day,
                time_slots=pending_slots,
                sports=["Tennis", "Free Play"],
                extra_player_count=1,
            )

            if success:
                # Save booked slots
                for time_slot in pending_slots:
                    save_booked_slot(day, time_slot)
                results["successful"].append((day, pending_slots))
            else:
                results["unavailable"].append((day, pending_slots))

    return results


def format_booking_results(results: dict) -> str:
    """Format booking results for notification.

    Args:
        results: Dictionary from run_bookings() with successful/unavailable/skipped

    Returns:
        Formatted string describing the booking results
    """
    lines = []

    if results["successful"]:
        lines.append(f"✓ Successfully booked {len(results['successful'])} day(s):")
        for day, slots in results["successful"]:
            lines.append(f"  - {day}: {', '.join(slots)}")

    if results["unavailable"]:
        lines.append(f"✗ No available slots for {len(results['unavailable'])} day(s):")
        for day, slots in results["unavailable"]:
            lines.append(f"  - {day}: {', '.join(slots)}")

    if results["skipped"]:
        lines.append(f"⊘ Skipped {len(results['skipped'])} day(s) (already booked):")
        for day, slots in results["skipped"]:
            lines.append(f"  - {day}: {', '.join(slots)}")

    return "\n".join(lines) if lines else "No bookings to process."


def main():
    """Main entry point for the application."""
    try:
        results = run_bookings()
        message = format_booking_results(results)
        logging.info("Booking results:\n%s", message)

        # Notify with results
        if results["successful"]:
            send_pushover_message(
                PUSHOVER_USER_KEY,
                PUSHOVER_API_TOKEN,
                message,
                title="Tennis Court Bookings - Success!",
            )
        elif results["unavailable"]:
            send_pushover_message(
                PUSHOVER_USER_KEY,
                PUSHOVER_API_TOKEN,
                message,
                title="Tennis Court Bookings - No Availability",
            )
        else:
            send_pushover_message(
                PUSHOVER_USER_KEY,
                PUSHOVER_API_TOKEN,
                message,
                title="Tennis Court Bookings - All Already Booked",
            )
    except Exception as e:
        logging.exception("Booking process failed")
        send_pushover_message(
            PUSHOVER_USER_KEY,
            PUSHOVER_API_TOKEN,
            f"Booking process failed with error:\n{e}",
            title="Tennis Court Bookings - Error",
        )
        raise


if __name__ == "__main__":
    main()
