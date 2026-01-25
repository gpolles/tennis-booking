# Tennis Book

An automated tennis court booking application that uses Playwright to book courts on PlayByPoint. The application logs in to your PlayByPoint account, selects available time slots, and confirms bookings automatically.

## Features

- Automated login to PlayByPoint
- Automated court booking for specified days and time slots
- Support for multiple sports (Tennis, Free Play, etc.)
- Tracking of already-booked slots to avoid duplicate bookings
- Configurable wait times to simulate natural user behavior
- Detailed logging of all booking activities

## Setup

1. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application requires environment variables for authentication and booking preferences:

### Required Environment Variables

- **`PLAYBYPOINT_EMAIL`**: Your PlayByPoint account email address
- **`PLAYBYPOINT_PASSWORD`**: Your PlayByPoint account password
- **`BOOKING_SLOTS`**: Booking slots configuration (see format below)

### Optional Environment Variables

- **`BOOKED_DATE_FILE`**: Path to a file for persisting booked slots (prevents duplicate bookings)

### Booking Slots Format

The `BOOKING_SLOTS` variable uses the following format:

```
day_slot1_slot2_...,day_slot1_slot2_...
```

**Examples:**

- Single slot: `Sun_8am` (books Sunday 8am)
- Multiple slots on one day: `Sun_8am_8:30am_9am` (books three slots on Sunday)
- Multiple days: `Sun_8am_8:30am,Tue_5pm_5:30pm` (books two days with different times)
- Complex: `Mon_6am_6:30am,Wed_7pm_7:30pm,Fri_6pm_6:30pm`

Days should be three-letter abbreviations: `Sun`, `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`

Times should be in 12-hour format: `8am`, `8:30am`, `5pm`, `5:30pm`, etc.

## Usage

Set the required environment variables and run the application:

```bash
export PLAYBYPOINT_EMAIL="your-email@example.com"
export PLAYBYPOINT_PASSWORD="your-password"
export BOOKING_SLOTS="Sun_8am_8:30am,Wed_6pm_6:30pm"
export BOOKED_DATE_FILE="$HOME/.tennis-book/booked-slots.txt"

python tennis-book.py
```

## How It Works

1. **Authentication**: Logs into your PlayByPoint account with provided credentials
2. **Navigation**: Navigates to the booking page
3. **Selection**: For each booking request, selects the specified day and time slots
4. **Booking**: Completes the booking with your preferred player count (default: 2 players including you)
5. **Persistence**: Saves successfully booked slots to a file to prevent duplicate bookings on future runs

## Notes

- The application includes random wait times between actions to simulate natural user behavior
- Each booking attempt tries both "Tennis" and "Free Play" sport types
- The application adds 1 extra player by default (total of 2 players per booking)
- Already booked slots are tracked and skipped on subsequent runs
- Check the log output for detailed information about booking results

## Dependencies

See `requirements.txt` for a list of dependencies.
