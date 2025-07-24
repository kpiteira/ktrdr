#!/usr/bin/env python3
"""
GPU Utilization Test Script

This script creates intensive GPU workloads to test maximum GPU utilization
on Apple Silicon Macs. Run this while monitoring Activity Monitor to see
if your GPU can reach higher utilization levels.
"""

import torch
import time
import sys

def test_gpu_utilization():
    """Test GPU utilization with increasingly intensive workloads."""
    
    if not torch.backends.mps.is_available():
        print("❌ MPS not available - cannot test GPU utilization")
        return False
    
    device = torch.device("mps")
    print(f"✅ Using device: {device}")
    print("🚀 Starting GPU utilization test...")
    print("📊 Monitor GPU usage in Activity Monitor while this runs")
    print()
    
    try:
        # Test 1: Small matrices (baseline)
        print("Test 1: Small matrices (1000x1000)...")
        for i in range(10):
            a = torch.randn(1000, 1000, device=device)
            b = torch.randn(1000, 1000, device=device)
            c = torch.matmul(a, b)
            print(f"  Iteration {i+1}/10")
            time.sleep(0.5)
        
        print()
        
        # Test 2: Medium matrices 
        print("Test 2: Medium matrices (3000x3000)...")
        for i in range(8):
            a = torch.randn(3000, 3000, device=device)
            b = torch.randn(3000, 3000, device=device)
            c = torch.matmul(a, b) + torch.matmul(b, a)
            print(f"  Iteration {i+1}/8")
            time.sleep(0.5)
        
        print()
        
        # Test 3: Large matrices (should stress GPU more)
        print("Test 3: Large matrices (5000x5000)...")
        for i in range(5):
            a = torch.randn(5000, 5000, device=device)
            b = torch.randn(5000, 5000, device=device)
            # Multiple operations to increase GPU load
            c = torch.matmul(a, b)
            d = torch.matmul(b, a)
            e = c + d
            f = torch.sin(e) * torch.cos(e)
            print(f"  Iteration {i+1}/5")
            time.sleep(1.0)
        
        print()
        
        # Test 4: Neural network simulation (most realistic)
        print("Test 4: Neural network simulation...")
        
        # Create a larger model similar to training
        class TestModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = torch.nn.Sequential(
                    torch.nn.Linear(100, 1024),
                    torch.nn.ReLU(),
                    torch.nn.Linear(1024, 512),
                    torch.nn.ReLU(),
                    torch.nn.Linear(512, 256),
                    torch.nn.ReLU(),
                    torch.nn.Linear(256, 10)
                )
            
            def forward(self, x):
                return self.layers(x)
        
        model = TestModel().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = torch.nn.CrossEntropyLoss()
        
        for i in range(20):
            # Large batch to stress GPU
            batch_size = 512
            x = torch.randn(batch_size, 100, device=device)
            y = torch.randint(0, 10, (batch_size,), device=device)
            
            # Forward pass
            outputs = model(x)
            loss = criterion(outputs, y)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            print(f"  Neural network iteration {i+1}/20, Loss: {loss.item():.4f}")
            time.sleep(0.2)
        
        print()
        print("✅ GPU utilization test completed!")
        print("📊 Check Activity Monitor - GPU usage should have increased significantly")
        print("🎯 If GPU usage stayed low (< 20%), your training workload might be:")
        print("   • Too small (increase batch size or model size)")
        print("   • CPU-bound (data loading/preprocessing bottleneck)")
        print("   • Memory-bound (not enough data to keep GPU busy)")
        
        return True
        
    except Exception as e:
        print(f"❌ GPU test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 GPU Utilization Test for Apple Silicon")
    print("=" * 50)
    
    if test_gpu_utilization():
        print("\n🚀 Test completed successfully!")
        print("💡 Compare this GPU usage to your training - if training shows much lower")
        print("   usage, we can optimize the training code further.")
    else:
        print("\n❌ Test failed!")
        sys.exit(1)