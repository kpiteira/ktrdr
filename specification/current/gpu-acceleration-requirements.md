# GPU Acceleration Requirements - Training Service Host Migration

**Document Version**: 1.2  
**Date**: January 2025  
**Status**: Draft  
**Author**: KTRDR Development Team

---

## 1. Executive Summary

### 1.1 Purpose
This document outlines the requirements for extracting the KTRDR training service from Docker to the host system to enable GPU acceleration, following the same pattern successfully used for the IB host service.

### 1.2 Current Situation
- **GPU acceleration is fully implemented** in `ktrdr/training/gpu_memory_manager.py` with MPS/CUDA support
- Training service runs inside Docker container, blocking access to host GPU resources
- Training speed limits overnight experiment iterations due to CPU-only execution
- IB host service successfully demonstrates the host extraction pattern (port 5001)

### 1.3 Proposed Solution
Extract the training service to run directly on the host system using the **existing GPU-enabled training code**, following the IB host service architecture pattern. No reimplementation of training or GPU code required.

### 1.4 Expected Benefits
- 3-5x faster training execution
- Ability to run more experiments overnight
- Better resource utilization
- Foundation for future GPU-intensive features

---

## 2. Business Requirements

### 2.1 Strategic Goals
- **BR-1**: Accelerate research iteration cycles by reducing training time
- **BR-2**: Utilize available GPU hardware efficiently
- **BR-3**: Maintain system stability during migration
- **BR-4**: Preserve all existing functionality

### 2.2 Success Criteria
- **BR-5**: Training speed improvement of at least 3x using existing GPU acceleration code
- **BR-6**: No disruption to existing workflows
- **BR-7**: Seamless integration with current system following IB host service patterns
- **BR-8**: Simple deployment and maintenance aligned with IB service management

---

## 3. Functional Requirements

### 3.1 Core Training Service Requirements

#### 3.1.1 Service Extraction
- **FR-1**: The system SHALL extract existing training code from Docker without modification
- **FR-2**: The system SHALL maintain identical API interface as current Docker implementation
- **FR-3**: The system SHALL support all existing training operations using current `ktrdr.training` modules
- **FR-4**: The system SHALL handle concurrent training requests with appropriate queue management
- **FR-5**: The system SHALL provide real-time training progress updates

#### 3.1.2 GPU Acceleration (Using Existing Implementation)
- **FR-6**: The system SHALL utilize the existing `GPUMemoryManager` without modification
- **FR-7**: The system SHALL leverage existing Apple Silicon MPS acceleration support
- **FR-8**: The system SHALL leverage existing NVIDIA CUDA acceleration support
- **FR-9**: The system SHALL use existing CPU fallback capabilities
- **FR-10**: The system SHALL expose existing GPU utilization metrics via `gpu_memory_manager.py`
- **FR-11**: The system SHALL use existing GPU memory management and optimization features

#### 3.1.3 Data Access
- **FR-12**: The system SHALL access the shared data directory used by Docker containers
- **FR-13**: The system SHALL read and write models to shared storage locations
- **FR-14**: The system SHALL maintain file permission compatibility with Docker containers
- **FR-15**: The system SHALL handle file locking for concurrent access

### 3.2 Integration Requirements

#### 3.2.1 API Compatibility (Following IB Host Service Pattern)
- **FR-16**: The Docker API SHALL route training requests to host service when enabled, similar to IB service pattern
- **FR-17**: The system SHALL require no changes to CLI commands
- **FR-18**: The system SHALL require no changes to frontend interfaces  
- **FR-19**: The system SHALL maintain backward compatibility with existing tests
- **FR-20**: The system SHALL support environment toggle for host service activation (like `USE_IB_HOST_SERVICE`)

#### 3.2.2 Service Communication
- **FR-21**: Services SHALL communicate using standard HTTP protocols (following IB service pattern)
- **FR-22**: Service discovery SHALL be configurable via environment variables (like `TRAINING_HOST_SERVICE_URL`)
- **FR-23**: The system SHALL implement retry logic for transient failures
- **FR-24**: The system SHALL implement circuit breaker patterns for service protection

### 3.3 Operational Requirements

#### 3.3.1 Service Management (Aligned with IB Host Service)
- **FR-25**: The system SHALL start automatically on system boot (upgrading from current manual IB service startup)
- **FR-26**: The system SHALL restart automatically on failure
- **FR-27**: The system SHALL provide graceful shutdown capabilities
- **FR-28**: The system SHALL follow IB host service management patterns with improvements for auto-startup

#### 3.3.2 Monitoring and Logging
- **FR-29**: The system SHALL provide health check endpoints (following IB service `/health` pattern)
- **FR-30**: The system SHALL expose metrics for monitoring (including existing GPU metrics)
- **FR-31**: The system SHALL implement structured logging consistent with IB service
- **FR-32**: The system SHALL provide training progress visibility using existing analytics

---

## 4. Non-Functional Requirements

### 4.1 Performance Requirements
- **NFR-1**: GPU-accelerated training SHALL be at least 3x faster than CPU training
- **NFR-2**: Service status queries SHALL respond within 100ms
- **NFR-3**: The system SHALL start within 10 seconds
- **NFR-4**: Memory usage SHALL not exceed 4GB baseline (excluding model memory)

### 4.2 Reliability Requirements
- **NFR-5**: The service SHALL maintain 99.9% uptime during operation
- **NFR-6**: The system SHALL complete in-flight requests during shutdown
- **NFR-7**: The system SHALL recover automatically from crashes
- **NFR-8**: The system SHALL preserve data integrity during failures

### 4.3 Security Requirements
- **NFR-9**: The service SHALL only accept connections from localhost
- **NFR-10**: The system SHALL implement authentication for API access
- **NFR-11**: The system SHALL validate all input parameters
- **NFR-12**: The system SHALL prevent arbitrary code execution

### 4.4 Compatibility Requirements
- **NFR-13**: The system SHALL support multiple GPU types (MPS, CUDA)
- **NFR-14**: The system SHALL run on both macOS and Linux
- **NFR-15**: The system SHALL maintain Python 3.11 compatibility
- **NFR-16**: The system SHALL minimize external dependencies

### 4.5 Maintainability Requirements
- **NFR-17**: The system SHALL provide clear error messages
- **NFR-18**: The system SHALL support configuration updates without restart
- **NFR-19**: The system SHALL maintain clear separation from Docker code
- **NFR-20**: The system SHALL support easy rollback to Docker-only operation

---

## 5. Constraints

### 5.1 Technical Constraints
- **TC-1**: Must maintain compatibility with existing KTRDR architecture
- **TC-2**: Must work within current data storage structure
- **TC-3**: Must support both development and production environments
- **TC-4**: Must handle Docker networking limitations

### 5.2 Operational Constraints
- **OC-1**: Must align with IB host service patterns
- **OC-2**: Must support single-developer deployment
- **OC-3**: Must work with existing monitoring infrastructure
- **OC-4**: Must maintain MVP simplicity principles

---

## 6. Assumptions

### 6.1 Technical Assumptions
- **TA-1**: Host system has compatible GPU hardware
- **TA-2**: PyTorch supports the available GPU type
- **TA-3**: Shared storage is accessible from both Docker and host
- **TA-4**: Network connectivity between Docker and host is reliable

### 6.2 Operational Assumptions
- **OA-1**: Developer has admin access to host system
- **OA-2**: Existing IB host service patterns are acceptable
- **OA-3**: Current API structure is suitable for proxying
- **OA-4**: Training workloads are GPU-acceleratable

---

## 7. Dependencies

### 7.1 System Dependencies
- **SD-1**: PyTorch with GPU support (MPS/CUDA)
- **SD-2**: Compatible GPU drivers installed
- **SD-3**: Python 3.11 environment on host
- **SD-4**: Shared filesystem between Docker and host

### 7.2 Integration Dependencies
- **ID-1**: Docker API for request proxying
- **ID-2**: IB host service for pattern reference
- **ID-3**: Existing training module interfaces
- **ID-4**: Current data management system

---

## 8. Risks

### 8.1 Technical Risks
- **TR-1**: GPU driver incompatibility
- **TR-2**: Memory management differences between CPU and GPU
- **TR-3**: Numerical differences in GPU computation
- **TR-4**: Performance regression in certain scenarios

### 8.2 Operational Risks
- **OR-1**: Increased system complexity
- **OR-2**: Debugging challenges across Docker/host boundary
- **OR-3**: Deployment complexity increase
- **OR-4**: Synchronization issues between services

---

## 9. Success Metrics

### 9.1 Performance Metrics
- **PM-1**: Training time reduction of 3x or greater
- **PM-2**: GPU utilization above 80% during training
- **PM-3**: No increase in error rates
- **PM-4**: API response times unchanged

### 9.2 Operational Metrics
- **OM-1**: Zero-downtime migration
- **OM-2**: All existing tests passing
- **OM-3**: No changes required to user workflows
- **OM-4**: Successful automatic recovery from failures

---

## 10. Out of Scope

The following items are explicitly out of scope for this requirements document:
- **OS-1**: Multi-GPU parallel training
- **OS-2**: Distributed training across machines
- **OS-3**: GPU-accelerated inference
- **OS-4**: Real-time model serving
- **OS-5**: Container-based GPU solutions
- **OS-6**: Cloud GPU integration

---

## 11. Future Considerations

### 11.1 Potential Extensions
- **FC-1**: Support for additional GPU types
- **FC-2**: Multi-GPU utilization
- **FC-3**: GPU-accelerated data preprocessing
- **FC-4**: Model serving on GPU

### 11.2 Scalability Considerations
- **FC-5**: Distributed training capabilities
- **FC-6**: GPU cluster support
- **FC-7**: Cloud GPU integration
- **FC-8**: Containerized GPU solutions

---

## 12. Harmonization Requirements

### 12.1 IB Host Service Alignment
- **HR-1**: Both services SHALL use consistent startup mechanisms
- **HR-2**: Both services SHALL implement automatic restart on failure
- **HR-3**: Both services SHALL start automatically on system boot
- **HR-4**: Both services SHALL use similar configuration patterns
- **HR-5**: Both services SHALL follow consistent logging standards
- **HR-6**: Both services SHALL use compatible monitoring approaches

### 12.2 Operational Consistency
- **HR-7**: Management scripts SHALL work for both services
- **HR-8**: Deployment procedures SHALL be similar
- **HR-9**: Troubleshooting approaches SHALL be consistent
- **HR-10**: Documentation SHALL follow same patterns

---

**Document History**
- v1.0 - Initial draft (January 2025)
- v1.1 - Removed implementation details, added harmonization requirements