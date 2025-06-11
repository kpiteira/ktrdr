#!/usr/bin/env python3
"""
Data Loading Improvements Demo

This script demonstrates the enhanced data loading system with:
1. Better error 162 classification (future dates vs pace violations)
2. Async operations with cancellation support
3. Real-time progress tracking
4. CLI integration

Run this to see all improvements in action.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from ktrdr.data.async_data_loader import get_async_data_loader
from ktrdr.data.data_manager import DataManager
from ktrdr.utils.timezone_utils import TimestampManager

console = Console()

async def demo_future_date_validation():
    """Demo #1: Future date validation prevents misclassified error 162s."""
    console.print("\n[bold blue]🔮 Demo 1: Future Date Validation[/bold blue]")
    
    dm = DataManager(enable_ib=True)
    
    # Try to load data for a future date (should fail gracefully)
    future_date = TimestampManager.now_utc() + timedelta(days=30)
    console.print(f"Attempting to load data for future date: {future_date}")
    
    try:
        df = dm.load_data(
            symbol="AAPL",
            timeframe="1h", 
            start_date=future_date,
            end_date=future_date + timedelta(days=1),
            mode="tail"
        )
        console.print("[red]❌ This should have failed![/red]")
    except Exception as e:
        if "FUTURE DATE REQUEST" in str(e):
            console.print("[green]✅ Future date validation working correctly![/green]")
            console.print(f"Error: {e}")
        else:
            console.print(f"[yellow]⚠️ Unexpected error: {e}[/yellow]")

async def demo_async_loading():
    """Demo #2: Async loading with progress tracking and cancellation."""
    console.print("\n[bold blue]🚀 Demo 2: Async Loading with Progress[/bold blue]")
    
    loader = get_async_data_loader()
    
    # Create a demo job
    job_id = loader.create_job(
        symbol="AAPL",
        timeframe="1h",
        start_date=TimestampManager.now_utc() - timedelta(days=7),
        end_date=TimestampManager.now_utc(),
        mode="tail"
    )
    
    console.print(f"Created job: {job_id}")
    
    # Demo progress tracking
    progress_updates = []
    
    def track_progress(progress_info):
        progress_updates.append({
            "percentage": progress_info.progress_percentage,
            "segment": progress_info.current_segment,
            "completed": progress_info.completed_segments,
            "total": progress_info.total_segments
        })
    
    # Start job with progress tracking
    console.print("Starting async data loading...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        
        task = progress.add_task("Loading data...", total=100)
        
        # Start the job
        await loader.start_job(job_id, track_progress)
        
        # Monitor progress
        while True:
            job_status = loader.get_job_status(job_id)
            if not job_status:
                break
                
            status = job_status["status"]
            percentage = job_status["progress_percentage"]
            current_segment = job_status["current_segment"]
            
            progress.update(
                task,
                completed=percentage,
                description=f"Loading AAPL ({current_segment or 'starting...'})"
            )
            
            if status in ["completed", "failed", "cancelled"]:
                break
                
            await asyncio.sleep(0.1)
    
    # Show final result
    final_status = loader.get_job_status(job_id)
    if final_status:
        console.print(f"\n[green]✅ Job completed with status: {final_status['status']}[/green]")
        console.print(f"Bars fetched: {final_status['bars_fetched']}")
        console.print(f"Duration: {final_status['duration_seconds']:.2f}s")

async def demo_job_management():
    """Demo #3: Job management and status tracking."""
    console.print("\n[bold blue]📋 Demo 3: Job Management[/bold blue]")
    
    loader = get_async_data_loader()
    
    # Create multiple demo jobs
    jobs = []
    symbols = ["AAPL", "GOOGL", "MSFT"]
    
    for symbol in symbols:
        job_id = loader.create_job(
            symbol=symbol,
            timeframe="1d",
            mode="tail"
        )
        jobs.append(job_id)
    
    console.print(f"Created {len(jobs)} demo jobs")
    
    # Show job status table
    job_list = loader.list_jobs()
    
    table = Table(title="Active Jobs")
    table.add_column("Job ID", style="cyan")
    table.add_column("Symbol", style="green")
    table.add_column("Timeframe", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Created", style="dim")
    
    for job in job_list[-len(jobs):]:  # Show only our demo jobs
        status_emoji = {
            "pending": "⏳",
            "running": "🔄", 
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🛑"
        }.get(job["status"], "❓")
        
        table.add_row(
            job["job_id"],
            job["symbol"],
            job["timeframe"],
            f"{status_emoji} {job['status']}",
            job["created_at"][:16].replace("T", " ")
        )
    
    console.print(table)
    
    # Demo cancellation
    if jobs:
        cancel_job = jobs[0]
        console.print(f"\nDemonstrating cancellation of job {cancel_job}")
        success = loader.cancel_job(cancel_job)
        if success:
            console.print("[green]✅ Cancellation requested successfully[/green]")
        else:
            console.print("[yellow]⚠️ Job already completed or not found[/yellow]")

def demo_cli_usage():
    """Demo #4: CLI command examples."""
    console.print("\n[bold blue]💻 Demo 4: CLI Usage Examples[/bold blue]")
    
    console.print("New async CLI commands:")
    console.print()
    
    examples = [
        ("Load data (clean output)", "uv run ktrdr load-data AAPL --timeframe 1h --mode tail"),
        ("Load with progress bar", "uv run ktrdr load-data AAPL --timeframe 1h --mode tail --progress"),
        ("Load with verbose logs", "uv run ktrdr load-data AAPL --timeframe 1h --mode tail --verbose"),
        ("Check job status", "uv run ktrdr data-status"),
        ("Check specific job", "uv run ktrdr data-status --job-id abc123"),
        ("Cancel a job", "uv run ktrdr cancel-data abc123"),
        ("Verbose job listing", "uv run ktrdr data-status --verbose")
    ]
    
    table = Table(title="CLI Command Examples")
    table.add_column("Description", style="cyan")
    table.add_column("Command", style="green")
    
    for desc, cmd in examples:
        table.add_row(desc, cmd)
    
    console.print(table)
    
    console.print("\n[bold yellow]💡 Output Control:[/bold yellow]")
    console.print("• Default: Clean output with minimal logging")
    console.print("• --progress: Adds real-time progress bars")
    console.print("• --verbose: Shows detailed backend logs")
    console.print("• Ctrl+C: Graceful cancellation support")
    console.print("• Jobs: Automatically cleaned up after 24 hours")

async def main():
    """Run all demos."""
    console.print("[bold green]🎯 Data Loading Improvements Demo[/bold green]")
    console.print("This demo shows the enhanced data loading system with:")
    console.print("• Better error 162 classification")
    console.print("• Async operations with cancellation")
    console.print("• Real-time progress tracking")
    console.print("• Enhanced CLI integration")
    
    try:
        # Run demos
        await demo_future_date_validation()
        await demo_async_loading()
        await demo_job_management()
        demo_cli_usage()
        
        console.print("\n[bold green]🎉 All demos completed successfully![/bold green]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Demo failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

if __name__ == "__main__":
    asyncio.run(main())