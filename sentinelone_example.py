import requests
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.layout import Layout
from rich.panel import Panel
import logging

# Set up rich logging (RichHandler is used for visually appealing logs)
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("rich")
console = Console()

API_TOKEN = ""
BASE_URL = ""

# Create a session for API requests
session = requests.Session()
session.headers.update({"Authorization": f"ApiToken {API_TOKEN}"})


def fetch_paginated_api_data(
    params: dict,
    endpoint: str,
    page_callback=None,
) -> list[dict]:
    """
    Fetch data from a paginated API endpoint, handling pagination and errors.

    Args:
        endpoint: API endpoint path (without base URL)
        params: Query parameters for the API request
        page_callback: Optional callback function called after each page is fetched

    Returns:
        list[dict]: List containing the API response data

    Raises:
        AirflowException: If the API request fails or credentials are missing
    """
    if params["siteIds"] == "":
        raise ValueError
    all_data = []
    cursor = None
    is_sites = endpoint == "sites"
    url = f"{BASE_URL}{endpoint}"
    page_count = 0
    try:
        while True:
            current_params = {**params, "cursor": cursor} if cursor else params
            response = session.get(url=url, params=current_params, timeout=60)
            response.raise_for_status()
            result = response.json()
            data_chunk = result["data"]["sites"] if is_sites else result["data"]
            all_data.extend(data_chunk)

            page_count += 1
            if page_callback:
                page_callback(page_count)  # Logging progress of page fetches

            # Get cursor for next page
            cursor = result.get("pagination", {}).get("nextCursor")
            if not cursor:
                break
            current_params["cursor"] = cursor

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")  # Logging API errors with Rich
        raise

    logger.info(
        f"Fetched a total of {len(all_data)} items for endpoint {endpoint}"
    )  # Logging fetch summary
    return all_data


def create_progress_table(progress_data: dict) -> Table:
    """Create a table showing progress for each site."""
    # This function is for Rich table visualization, not core functionality
    table = Table(title="Site Details")
    table.add_column("Site ID", style="cyan", no_wrap=True)
    table.add_column("Total Records", style="magenta")
    table.add_column("Domain Name", style="green")
    table.add_column("Pages", style="blue")
    table.add_column("Status", style="bold")

    for site_id, data in progress_data.items():
        table.add_row(
            site_id,
            str(data["total_records"]),
            data["domain_name"],
            str(data["pages"]),
            data["status"],
        )
    return table


def create_progress_layout(overall_progress: Progress, progress_data: dict) -> Layout:
    """Create the layout combining overall progress bar and site details table."""
    # This function is for Rich layout and visualization, not core functionality
    layout = Layout()
    layout.split_column(
        Layout(
            Panel(overall_progress, title="Overall Progress"), size=3
        ),  # Progress bar visualization
        Layout(create_progress_table(progress_data)),  # Table visualization
    )
    return layout


def create_overall_progress() -> Progress:
    """Create and return the overall progress bar."""
    # This function is for Rich progress bar visualization, not core functionality
    overall_progress = Progress(
        TextColumn("[bold blue]Processing Sites", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TextColumn("{task.completed}/{task.total} sites"),
        TimeRemainingColumn(),
    )
    return overall_progress


def extract_alerts(site_map: dict) -> list[dict]:
    """Extract alerts for multiple sites with progress tracking."""
    results = []
    # Track progress data for each site
    progress_data = {}

    # Get the sites to process
    sites_to_process = list(site_map.items())[5:40]
    total_sites = len(sites_to_process)

    # Create overall progress bar
    overall_progress = create_overall_progress()
    overall_task = overall_progress.add_task("Sites", total=total_sites)

    try:
        with Live(
            create_progress_layout(
                overall_progress, progress_data
            ),  # Rich live layout for progress and table
            refresh_per_second=4,
            screen=True,
        ) as live:
            for site_id, domain_name in sites_to_process:
                # Initialize progress data for this site
                progress_data[site_id] = {
                    "domain_name": domain_name,
                    "total_records": 0,
                    "pages": 0,
                    "status": "[yellow]Running...[/yellow]",
                }
                live.update(
                    create_progress_layout(overall_progress, progress_data)
                )  # Update Rich layout

                def update_page_count(pages):
                    progress_data[site_id]["pages"] = pages
                    live.update(
                        create_progress_layout(overall_progress, progress_data)
                    )  # Update Rich layout

                try:
                    site_data = fetch_paginated_api_data(
                        params={"siteIds": site_id, "limit": 1000},
                        endpoint="cloud-detection/alerts",
                        page_callback=update_page_count,
                    )
                    results.extend(site_data)
                    progress_data[site_id]["total_records"] = len(site_data)
                    progress_data[site_id]["status"] = (
                        "[green]Completed[/green]"  # Rich status update
                    )
                except ValueError as ve:
                    progress_data[site_id]["total_records"] = 0
                    progress_data[site_id]["status"] = (
                        "[red]Failed[/red]"  # Rich status update
                    )
                    logger.error(
                        f"Error processing site {site_id} ({domain_name}): {ve}"
                    )  # Logging error with Rich

                # Update overall progress bar (Rich)
                overall_progress.update(overall_task, advance=1)
                live.update(
                    create_progress_layout(overall_progress, progress_data)
                )  # Update Rich layout

    except KeyboardInterrupt:
        logger.warning(
            "Process interrupted by user (Ctrl+C)"
        )  # Logging interruption with Rich
        console.print(
            "\n[yellow]Process interrupted by user. Returning partial results.[/yellow]"  # Rich console output
        )
    return results


if __name__ == "__main__":
    site_map = {}
    alerts = extract_alerts(site_map)
    console.print(
        "\n[green]Alerts were extracted :)[/green]",  # Rich console output
    )
