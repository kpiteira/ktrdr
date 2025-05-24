# KTRDR Indicator & Fuzzy Logic Integration Tasks

This document outlines the tasks related to indicator configuration, fuzzy logic integration, and their implementation in the API and frontend.

---

## Slice 9: Indicator Configuration & API (v1.0.9)

**Value delivered:** Comprehensive indicator configuration and calculation capabilities exposed through the API and frontend.

### Indicator API Enhancement
- [ ] **Task 9.1**: Expand indicator API endpoints
  - [ ] Create `/api/v1/indicators/metadata` endpoint for detailed indicator information
  - [ ] Implement `/api/v1/indicators/parameters` endpoint for parameter validation
  - [ ] Add `/api/v1/indicators/presets` endpoint for common configurations
  - [ ] Create batch calculation endpoint for multiple indicators
  - [ ] Implement efficient calculation with caching
  - [ ] Add parameter validation with detailed error messages
  - [ ] Create examples and documentation for all endpoints

- [ ] **Task 9.2**: Develop indicator service enhancements
  - [ ] Implement advanced parameter validation in service layer
  - [ ] Create service methods for indicator metadata retrieval
  - [ ] Add caching for frequently used indicator calculations
  - [ ] Implement efficient data transformation between formats
  - [ ] Create performance tracking for calculation times
  - [ ] Add detailed logging for debugging calculations
  - [ ] Implement error recovery strategies for calculation failures

### Frontend Indicator Components
- [ ] **Task 9.3**: Create indicator configuration UI
  - [ ] Implement IndicatorSelector component with search
  - [ ] Create IndicatorParameters component for configuration
  - [ ] Add parameter validation with instant feedback
  - [ ] Implement IndicatorPresets for common configurations
  - [ ] Create drag-and-drop reordering of indicators
  - [ ] Add indicator group management
  - [ ] Implement configuration persistence in state

- [ ] **Task 9.4**: Develop indicator state management
  - [ ] Create indicators slice in Redux store
  - [ ] Implement async thunks for indicator calculation
  - [ ] Add indicator selection actions and reducers
  - [ ] Create parameter update logic with validation
  - [ ] Implement indicator removal and reordering
  - [ ] Add preset management with saving/loading
  - [ ] Create error handling for indicator operations

### Indicator Visualization
- [ ] **Task 9.5**: Enhance chart integration with indicators
  - [ ] Create indicator series mapping for different visualization types
  - [ ] Implement indicator visibility toggles with state persistence
  - [ ] Add indicator color and style customization
  - [ ] Create indicator value tooltips with detailed information
  - [ ] Implement automatic scaling for indicator panels
  - [ ] Add indicator overlay transparency controls
  - [ ] Create synchronized highlighting between indicators

### Indicator Management
- [ ] **Task 9.6**: Implement indicator management features
  - [ ] Create saved indicator configurations with naming
  - [ ] Implement import/export of indicator settings
  - [ ] Add indicator comparison tools
  - [ ] Create indicator template system
  - [ ] Implement batch indicator configuration
  - [ ] Add indicator documentation display
  - [ ] Create indicator performance metrics

### Testing
- [ ] **Task 9.7**: Implement indicator testing
  - [ ] Create API endpoint tests with known values
  - [ ] Add service layer tests for indicator calculations
  - [ ] Implement UI component tests for indicator configuration
  - [ ] Create integration tests for the complete indicator flow
  - [ ] Add performance benchmarks for indicator calculations
  - [ ] Implement visual tests for indicator rendering
  - [ ] Create test fixtures for common indicator patterns

### Deliverable
A comprehensive indicator system that:
- Provides detailed metadata about available indicators
- Allows flexible configuration of indicator parameters
- Calculates indicator values efficiently with proper validation
- Displays indicators in various visualization formats
- Offers preset configurations for common scenarios
- Provides a smooth user experience for indicator management

Example indicator configuration:
```tsx
// IndicatorConfiguration.tsx
import React, { useState } from 'react';
import { useGetIndicatorsMetadataQuery } from '../api/indicatorsApi';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { addIndicator, updateIndicatorParams } from '../store/indicatorsSlice';
import { Card, Select, Input, Button, Tabs } from '../components/common';

export const IndicatorConfiguration: React.FC = () => {
  const dispatch = useAppDispatch();
  const selectedIndicators = useAppSelector(state => state.indicators.selected);
  const { data: indicatorsMetadata, isLoading } = useGetIndicatorsMetadataQuery();
  const [selectedType, setSelectedType] = useState<string>('');
  const [parameters, setParameters] = useState<Record<string, any>>({});
  
  if (isLoading || !indicatorsMetadata) return <div>Loading indicators...</div>;
  
  const currentMetadata = indicatorsMetadata.find(i => i.name === selectedType);
  
  const handleAddIndicator = () => {
    if (selectedType && currentMetadata) {
      dispatch(addIndicator({
        id: Date.now().toString(),
        type: selectedType,
        parameters: { ...parameters }
      }));
      // Reset form
      setSelectedType('');
      setParameters({});
    }
  };
  
  return (
    <Card title="Indicator Configuration">
      <Tabs 
        tabs={[
          { key: 'new', label: 'Add New', content: (
            <>
              <Select
                label="Indicator Type"
                value={selectedType}
                onChange={setSelectedType}
                options={indicatorsMetadata.map(i => ({ value: i.name, label: i.displayName }))}
              />
              
              {currentMetadata && (
                <div className="parameters">
                  <h4>Parameters</h4>
                  {currentMetadata.parameters.map(param => (
                    <Input
                      key={param.name}
                      label={param.displayName}
                      type={param.type === 'number' ? 'number' : 'text'}
                      value={parameters[param.name] ?? param.defaultValue}
                      onChange={value => setParameters({...parameters, [param.name]: value })}
                      help={param.description}
                    />
                  ))}
                  <Button onClick={handleAddIndicator}>Add Indicator</Button>
                </div>
              )}
            </>
          )},
          { key: 'active', label: 'Active Indicators', content: (
            <div className="active-indicators">
              {selectedIndicators.map(indicator => (
                <div key={indicator.id} className="indicator-item">
                  <h4>{indicatorsMetadata.find(i => i.name === indicator.type)?.displayName}</h4>
                  <div className="parameters">
                    {/* Parameter editing UI for active indicators */}
                  </div>
                </div>
              ))}
            </div>
          )}
        ]}
      />
    </Card>
  );
};
```

---

## Slice 10: Fuzzy Logic Integration (v1.0.10)

**Value delivered:** Integration of fuzzy logic capabilities into the API and frontend, allowing visualization and configuration of fuzzy sets.

### Fuzzy Logic API
- [ ] **Task 10.1**: Implement fuzzy logic API endpoints
  - [ ] Create `/api/v1/fuzzy/sets` endpoint for fuzzy set metadata
  - [ ] Implement `/api/v1/fuzzy/evaluate` endpoint for fuzzy evaluation
  - [ ] Add `/api/v1/fuzzy/presets` endpoint for common fuzzy configurations
  - [ ] Create parameter validation for fuzzy set parameters
  - [ ] Implement detailed documentation with examples
  - [ ] Add error handling specific to fuzzy calculations
  - [ ] Create batch processing for efficient evaluation

- [ ] **Task 10.2**: Develop fuzzy service layer
  - [ ] Create FuzzyService with comprehensive adapter methods
  - [ ] Implement fuzzy set parameter validation
  - [ ] Add efficient evaluation with vectorized operations
  - [ ] Create caching for repeated fuzzy evaluations
  - [ ] Implement result formatting with proper metadata
  - [ ] Add comprehensive logging for debugging
  - [ ] Create performance tracking for evaluations

### Fuzzy Logic Frontend Components
- [ ] **Task 10.3**: Implement fuzzy set management UI
  - [ ] Create FuzzySetEditor component for visual editing
  - [ ] Implement MembershipFunctionGraph for visualization
  - [ ] Add parameter inputs with instant preview
  - [ ] Create preset management with saving/loading
  - [ ] Implement set combination previews
  - [ ] Add export/import functionality for configurations
  - [ ] Create documentation integration for fuzzy concepts

- [ ] **Task 10.4**: Develop fuzzy state management
  - [ ] Create fuzzy slice in Redux store
  - [ ] Implement actions for fuzzy set configuration
  - [ ] Add async thunks for fuzzy evaluation
  - [ ] Create selectors for fuzzy state access
  - [ ] Implement middleware for side effects
  - [ ] Add persistence for fuzzy configurations
  - [ ] Create error handling for fuzzy operations

### Fuzzy Visualization
- [ ] **Task 10.5**: Implement fuzzy visualization components
  - [ ] Create FuzzyHighlightBand component for chart integration
  - [ ] Implement color gradient visualization for membership degrees
  - [ ] Add interactive hover tooltips with fuzzy values
  - [ ] Create time-series visualization of fuzzy membership
  - [ ] Implement membership function graph component
  - [ ] Add synchronized highlighting across charts
  - [ ] Create visualization settings for customization

- [ ] **Task 10.6**: Develop fuzzy-indicator integration
  - [ ] Create binding between indicators and fuzzy inputs
  - [ ] Implement real-time fuzzy evaluation on indicator changes
  - [ ] Add visual linking between indicators and fuzzy sets
  - [ ] Create transition animations for membership changes
  - [ ] Implement intelligent layout for fuzzy visualizations
  - [ ] Add combined view of indicators and fuzzy memberships
  - [ ] Create detailed tooltips with combined information

### Testing
- [ ] **Task 10.7**: Create fuzzy logic tests
  - [ ] Implement unit tests for API endpoints
  - [ ] Add service layer tests with known values
  - [ ] Create component tests for fuzzy UI elements
  - [ ] Implement integration tests for fuzzy evaluation flow
  - [ ] Add visual tests for fuzzy visualization components
  - [ ] Create performance benchmarks for fuzzy operations
  - [ ] Implement comprehensive test fixtures for fuzzy sets

### Deliverable
A comprehensive fuzzy logic system that:
- Allows creation and configuration of fuzzy membership functions
- Visualizes fuzzy sets with interactive graphs
- Evaluates indicator values through fuzzy logic
- Displays fuzzy membership as color bands on charts
- Provides preset configurations for common scenarios
- Offers educational resources about fuzzy logic concepts

Example fuzzy set editor:
```tsx
// FuzzySetEditor.tsx
import React, { useState } from 'react';
import { useGetFuzzySetsQuery, useUpdateFuzzySetMutation } from '../api/fuzzyApi';
import { MembershipFunctionGraph } from './MembershipFunctionGraph';
import { Card, Select, RangeSlider, Button } from '../components/common';

interface FuzzySetEditorProps {
  indicatorId: string;
}

export const FuzzySetEditor: React.FC<FuzzySetEditorProps> = ({ indicatorId }) => {
  const { data: fuzzySets, isLoading } = useGetFuzzySetsQuery(indicatorId);
  const [updateFuzzySet] = useUpdateFuzzySetMutation();
  const [selectedSet, setSelectedSet] = useState<string>('');
  const [parameters, setParameters] = useState<number[]>([]);
  
  if (isLoading || !fuzzySets) return <div>Loading fuzzy sets...</div>;
  
  const currentSet = fuzzySets.find(set => set.name === selectedSet);
  
  const handleParameterChange = (index: number, value: number) => {
    const newParams = [...parameters];
    newParams[index] = value;
    setParameters(newParams);
  };
  
  const handleSave = () => {
    if (selectedSet && parameters.length > 0) {
      updateFuzzySet({
        indicatorId,
        setName: selectedSet,
        parameters
      });
    }
  };
  
  return (
    <Card title="Fuzzy Set Configuration">
      <Select
        label="Fuzzy Set"
        value={selectedSet}
        onChange={(value) => {
          setSelectedSet(value);
          const set = fuzzySets.find(s => s.name === value);
          if (set) setParameters([...set.parameters]);
        }}
        options={fuzzySets.map(set => ({ value: set.name, label: set.displayName }))}
      />
      
      {currentSet && (
        <>
          <MembershipFunctionGraph
            type={currentSet.type}
            parameters={parameters}
            width={400}
            height={200}
          />
          
          <div className="parameters">
            {parameters.map((param, index) => (
              <RangeSlider
                key={index}
                label={`Parameter ${index + 1}`}
                min={0}
                max={100}
                value={param}
                onChange={(value) => handleParameterChange(index, value)}
              />
            ))}
          </div>
          
          <Button onClick={handleSave}>Save Configuration</Button>
        </>
      )}
    </Card>
  );
};
```