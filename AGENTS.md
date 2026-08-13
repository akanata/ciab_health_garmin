# OpenHost Health Producer for Garmin

This application implements a producer for the OpenHost health data spec from
Garmin devices. The Garmin API itself is locked behind a developer application
portal, so data is extracted using python-garminconnect.

## Important References
- OpenHost Health Data service spec: https://github.com/imbue-openhost/health-data-service-spec
- python-garminconnect (unofficial API): https://github.com/cyberjunky/python-garminconnect
- GarminDB (alternative API): https://github.com/tcgoetz/GarminDB

## Development Commands

Always run these exact commands for project tasks:
- **Enter virtual environment:** `source venv/bin/activate` (always run at the start of each prompt)
- **Install dependencies:** `pip install`
- **Run local dev server:** `python -m http.server 8080`
- **Run build:** `python3 -m build`
- **Run linter/formatter:** `ruff check .`
- **Execute test suite:** `python -m unittest`

## Code Style & Architecture

Follow these precise rules when writing or modifying code:
- **Language & Framework:** Use Python.
- **Formatting:** Enforce 2-space indentation, semicolons, and single quotes. Max 80 characters per line.
- **Exports:** Always use named exports rather than default exports.
- **Styling:** Use Tailwind CSS utility classes; avoid inline styles or CSS modules.

## Project Structure

Directory layout rules to maintain:
- `src/app/` - Page routes and layout components.
- `src/components/ui/` - Shared atomic UI elements (Shadcn/radix).
- `src/hooks/` - Reusable custom React hooks.
- `src/lib/` - Third-party clients, database initialization, and utilities.

## Critical Guardrails & Gotchas

None yet, will populate as project evolves.