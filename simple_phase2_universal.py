#!/usr/bin/env python3
"""
Simple Phase 2 Universal Test

Quick test to verify universal architecture works in practice.
"""

import sys
import torch
from rich.console import Console

console = Console()

def simple_phase2_test():
    """Simple test of Phase 2 with universal architecture."""
    console.print("🧠 [bold cyan]Simple Phase 2 Universal Test[/bold cyan]")
    
    try:
        # Use the CLI directly for simplicity
        console.print("Testing via CLI command...")
        
        import subprocess
        import os
        
        # Change to project directory
        os.chdir("/Users/karl/Documents/dev/ktrdr2")
        
        # Run training command with very short period
        cmd = [
            "uv", "run", "python", "-m", "ktrdr.cli.main",
            "models", "train",
            "strategies/universal_zero_shot_model.yaml",
            "--symbols", "EURUSD,GBPUSD",
            "--timeframes", "1h", 
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-10",  # Very short for quick test
        ]
        
        console.print(f"Running: {' '.join(cmd)}")
        
        # Run with timeout
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=180  # 3 minute timeout
        )
        
        if result.returncode == 0:
            console.print("✅ [green]Training completed successfully![/green]")
            console.print("Output:")
            print(result.stdout)
            
            # Check if model was created
            from pathlib import Path
            models_dir = Path("models")
            if models_dir.exists():
                model_dirs = list(models_dir.glob("**/"))
                console.print(f"Found {len(model_dirs)} model directories")
                
                # Find the most recent model
                universal_models = [d for d in model_dirs if "universal" in d.name.lower()]
                if universal_models:
                    console.print(f"✅ Universal model created: {universal_models[0]}")
                    return True
                else:
                    console.print("⚠️  No universal model directories found")
                    
        else:
            console.print("❌ [red]Training failed[/red]")
            console.print("STDOUT:")
            print(result.stdout)
            console.print("STDERR:")  
            print(result.stderr)
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        console.print("⏰ [yellow]Training timed out - this is expected for large datasets[/yellow]")
        return False
    except Exception as e:
        console.print(f"❌ [red]Test failed: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = simple_phase2_test()
    if success:
        console.print("\n🎯 [bold green]Phase 2 Universal Architecture Working![/bold green]")
    else:
        console.print("\n❌ [bold red]Phase 2 needs debugging[/bold red]")