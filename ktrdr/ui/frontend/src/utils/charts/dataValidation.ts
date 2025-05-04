/**
 * Chart Data Validation
 * 
 * Provides comprehensive validation utilities for chart data to prevent errors during rendering.
 */
import { OHLCVData } from '../../types/data';
import { CandlestickData, LineData, HistogramData, BarData } from 'lightweight-charts';

/**
 * Validation error types
 */
export enum ValidationErrorType {
  MISSING_DATA = 'missing_data',
  INVALID_TYPE = 'invalid_type',
  ARRAY_LENGTH_MISMATCH = 'array_length_mismatch',
  INVALID_DATE = 'invalid_date',
  NON_NUMERIC_VALUE = 'non_numeric_value',
  INVALID_OHLC_RELATIONSHIP = 'invalid_ohlc_relationship',
  NEGATIVE_VALUE = 'negative_value',
  METADATA_ERROR = 'metadata_error',
  EMPTY_DATA = 'empty_data',
}

/**
 * Result of a validation operation
 */
export interface ValidationResult {
  /** Overall validation status */
  valid: boolean;
  /** List of validation issues */
  issues: ValidationIssue[];
  /** Summary of issues by type */
  summary: {
    [key in ValidationErrorType]?: number;
  };
  /** Percentage of data points with issues (0-100) */
  errorPercentage: number;
  /** Whether the issues are severe enough to prevent rendering */
  preventRendering: boolean;
}

/**
 * Individual validation issue
 */
export interface ValidationIssue {
  /** Type of validation error */
  type: ValidationErrorType;
  /** Description of the issue */
  message: string;
  /** Index in the data array (if applicable) */
  index?: number;
  /** Field name with the issue (if applicable) */
  field?: string;
  /** Severity of the issue (1 = warning, 2 = error, 3 = critical) */
  severity: 1 | 2 | 3;
}

/**
 * Options for data validation
 */
export interface ValidationOptions {
  /** Whether to validate OHLC relationships (high > low, etc.) */
  validateOHLCRelationships?: boolean;
  /** Whether to validate for negative values */
  validateNegativeValues?: boolean;
  /** Whether to allow missing volume values */
  allowMissingVolume?: boolean;
  /** Whether to validate metadata */
  validateMetadata?: boolean;
  /** Maximum percentage of errors allowed before preventing rendering */
  maxErrorPercentage?: number;
}

/**
 * Default validation options
 */
const DEFAULT_VALIDATION_OPTIONS: ValidationOptions = {
  validateOHLCRelationships: true,
  validateNegativeValues: true,
  allowMissingVolume: true,
  validateMetadata: true,
  maxErrorPercentage: 10, // 10% error threshold
};

/**
 * Validates OHLCV data
 * @param data OHLCV data to validate
 * @param options Validation options
 * @returns Validation result
 */
export const validateOHLCVData = (
  data: OHLCVData,
  options: ValidationOptions = DEFAULT_VALIDATION_OPTIONS
): ValidationResult => {
  const issues: ValidationIssue[] = [];
  const mergedOptions = { ...DEFAULT_VALIDATION_OPTIONS, ...options };
  
  // Check if data is defined
  if (!data) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data is undefined or null',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Check for required properties
  if (!data.dates) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data missing "dates" property',
      severity: 3,
    });
  }
  
  if (!data.ohlcv) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data missing "ohlcv" property',
      severity: 3,
    });
  }
  
  // Check if arrays are empty
  if (data.dates && data.dates.length === 0) {
    issues.push({
      type: ValidationErrorType.EMPTY_DATA,
      message: 'Dates array is empty',
      severity: 3,
    });
  }
  
  if (data.ohlcv && data.ohlcv.length === 0) {
    issues.push({
      type: ValidationErrorType.EMPTY_DATA,
      message: 'OHLCV array is empty',
      severity: 3,
    });
  }
  
  // If critical properties are missing, no need to validate further
  if (issues.some(issue => issue.severity === 3)) {
    return createValidationResult(issues, 0);
  }
  
  // Check if required properties are arrays
  if (!Array.isArray(data.dates)) {
    issues.push({
      type: ValidationErrorType.INVALID_TYPE,
      message: 'Property "dates" is not an array',
      severity: 3,
    });
  }
  
  if (!Array.isArray(data.ohlcv)) {
    issues.push({
      type: ValidationErrorType.INVALID_TYPE,
      message: 'Property "ohlcv" is not an array',
      severity: 3,
    });
  }
  
  // If arrays are invalid, no need to validate further
  if (issues.some(issue => issue.severity === 3)) {
    return createValidationResult(issues, 0);
  }
  
  // Check array lengths match
  if (data.dates.length !== data.ohlcv.length) {
    issues.push({
      type: ValidationErrorType.ARRAY_LENGTH_MISMATCH,
      message: `Array length mismatch: dates (${data.dates.length}) vs ohlcv (${data.ohlcv.length})`,
      severity: 3,
    });
    
    // Cannot validate further if lengths don't match
    return createValidationResult(issues, 0);
  }
  
  // Track data points with issues for error percentage calculation
  let pointsWithIssues = 0;
  const totalPoints = data.dates.length;
  
  // Validate date values
  for (let i = 0; i < data.dates.length; i++) {
    const date = data.dates[i];
    let hasIssue = false;
    
    if (typeof date !== 'string' && typeof date !== 'number') {
      issues.push({
        type: ValidationErrorType.INVALID_DATE,
        message: `Invalid date type at index ${i}: ${typeof date}`,
        index: i,
        field: 'date',
        severity: 2,
      });
      hasIssue = true;
    } else if (typeof date === 'string') {
      const timestamp = new Date(date).getTime();
      if (isNaN(timestamp)) {
        issues.push({
          type: ValidationErrorType.INVALID_DATE,
          message: `Invalid date string at index ${i}: "${date}"`,
          index: i,
          field: 'date',
          severity: 2,
        });
        hasIssue = true;
      }
    }
    
    if (hasIssue) {
      pointsWithIssues++;
    }
  }
  
  // Validate OHLCV data structure
  for (let i = 0; i < data.ohlcv.length; i++) {
    const ohlcv = data.ohlcv[i];
    let hasIssue = false;
    
    if (!Array.isArray(ohlcv)) {
      issues.push({
        type: ValidationErrorType.INVALID_TYPE,
        message: `OHLCV data at index ${i} is not an array`,
        index: i,
        severity: 2,
      });
      pointsWithIssues++;
      continue;
    }
    
    if (ohlcv.length !== 5) {
      issues.push({
        type: ValidationErrorType.ARRAY_LENGTH_MISMATCH,
        message: `OHLCV data at index ${i} has incorrect length: ${ohlcv.length} (expected 5)`,
        index: i,
        severity: 2,
      });
      hasIssue = true;
    }
    
    // Check for non-numeric values
    const fieldNames = ['open', 'high', 'low', 'close', 'volume'];
    
    for (let j = 0; j < Math.min(ohlcv.length, 5); j++) {
      // Skip volume if allowMissingVolume is true
      if (j === 4 && mergedOptions.allowMissingVolume && (ohlcv[j] === null || ohlcv[j] === undefined)) {
        continue;
      }
      
      if (typeof ohlcv[j] !== 'number' || isNaN(ohlcv[j])) {
        issues.push({
          type: ValidationErrorType.NON_NUMERIC_VALUE,
          message: `Non-numeric ${fieldNames[j]} value at index ${i}: ${ohlcv[j]}`,
          index: i,
          field: fieldNames[j],
          severity: 2,
        });
        hasIssue = true;
      }
    }
    
    // Only perform these checks if all values are numeric
    if (!hasIssue && mergedOptions.validateOHLCRelationships) {
      const [open, high, low, close] = ohlcv;
      
      // Check OHLC relationships
      if (high < low) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: high (${high}) is less than low (${low})`,
          index: i,
          severity: 2,
        });
        hasIssue = true;
      }
      
      if (high < open || high < close) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: high (${high}) is not the highest value`,
          index: i,
          severity: 1, // Warning, not error
        });
        hasIssue = true;
      }
      
      if (low > open || low > close) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: low (${low}) is not the lowest value`,
          index: i,
          severity: 1, // Warning, not error
        });
        hasIssue = true;
      }
    }
    
    // Check for negative values
    if (!hasIssue && mergedOptions.validateNegativeValues) {
      // Check for negative volume
      if (ohlcv[4] < 0) {
        issues.push({
          type: ValidationErrorType.NEGATIVE_VALUE,
          message: `Negative volume at index ${i}: ${ohlcv[4]}`,
          index: i,
          field: 'volume',
          severity: 1,
        });
        hasIssue = true;
      }
    }
    
    if (hasIssue) {
      pointsWithIssues++;
    }
  }
  
  // Validate metadata
  if (mergedOptions.validateMetadata && data.metadata) {
    if (!data.metadata.symbol) {
      issues.push({
        type: ValidationErrorType.METADATA_ERROR,
        message: 'Metadata missing "symbol" property',
        field: 'metadata.symbol',
        severity: 1,
      });
    }
    
    if (!data.metadata.timeframe) {
      issues.push({
        type: ValidationErrorType.METADATA_ERROR,
        message: 'Metadata missing "timeframe" property',
        field: 'metadata.timeframe',
        severity: 1,
      });
    }
    
    if (data.metadata.points !== data.dates.length) {
      issues.push({
        type: ValidationErrorType.METADATA_ERROR,
        message: `Metadata "points" (${data.metadata.points}) doesn't match actual data length (${data.dates.length})`,
        field: 'metadata.points',
        severity: 1,
      });
    }
  }
  
  // Calculate error percentage
  const errorPercentage = totalPoints > 0 ? (pointsWithIssues / totalPoints) * 100 : 0;
  
  return createValidationResult(issues, errorPercentage);
};

/**
 * Validates formatted candlestick data
 * @param data Candlestick data to validate
 * @returns Validation result
 */
export const validateCandlestickData = (
  data: CandlestickData[]
): ValidationResult => {
  const issues: ValidationIssue[] = [];
  
  // Check if data is defined
  if (!data) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data is undefined or null',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Check if array is empty
  if (data.length === 0) {
    issues.push({
      type: ValidationErrorType.EMPTY_DATA,
      message: 'Candlestick data array is empty',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Track data points with issues for error percentage calculation
  let pointsWithIssues = 0;
  const totalPoints = data.length;
  
  // Validate each data point
  for (let i = 0; i < data.length; i++) {
    const point = data[i];
    let hasIssue = false;
    
    // Check for required properties
    if (!point.time) {
      issues.push({
        type: ValidationErrorType.MISSING_DATA,
        message: `Missing "time" at index ${i}`,
        index: i,
        field: 'time',
        severity: 2,
      });
      hasIssue = true;
    }
    
    // Check for numeric values
    const fields = ['open', 'high', 'low', 'close'] as const;
    for (const field of fields) {
      if (typeof point[field] !== 'number' || isNaN(point[field])) {
        issues.push({
          type: ValidationErrorType.NON_NUMERIC_VALUE,
          message: `Non-numeric ${field} value at index ${i}: ${point[field]}`,
          index: i,
          field,
          severity: 2,
        });
        hasIssue = true;
      }
    }
    
    // Skip relationship checks if numeric validation failed
    if (!hasIssue) {
      // Check OHLC relationships
      if (point.high < point.low) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: high (${point.high}) is less than low (${point.low})`,
          index: i,
          severity: 2,
        });
        hasIssue = true;
      }
      
      if (point.high < point.open || point.high < point.close) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: high (${point.high}) is not the highest value`,
          index: i,
          severity: 1,
        });
        hasIssue = true;
      }
      
      if (point.low > point.open || point.low > point.close) {
        issues.push({
          type: ValidationErrorType.INVALID_OHLC_RELATIONSHIP,
          message: `Invalid OHLC at index ${i}: low (${point.low}) is not the lowest value`,
          index: i,
          severity: 1,
        });
        hasIssue = true;
      }
    }
    
    if (hasIssue) {
      pointsWithIssues++;
    }
  }
  
  // Calculate error percentage
  const errorPercentage = totalPoints > 0 ? (pointsWithIssues / totalPoints) * 100 : 0;
  
  return createValidationResult(issues, errorPercentage);
};

/**
 * Validates formatted line data
 * @param data Line data to validate
 * @returns Validation result
 */
export const validateLineData = (
  data: LineData[]
): ValidationResult => {
  const issues: ValidationIssue[] = [];
  
  // Check if data is defined
  if (!data) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data is undefined or null',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Check if array is empty
  if (data.length === 0) {
    issues.push({
      type: ValidationErrorType.EMPTY_DATA,
      message: 'Line data array is empty',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Track data points with issues for error percentage calculation
  let pointsWithIssues = 0;
  const totalPoints = data.length;
  
  // Validate each data point
  for (let i = 0; i < data.length; i++) {
    const point = data[i];
    let hasIssue = false;
    
    // Check for required properties
    if (!point.time) {
      issues.push({
        type: ValidationErrorType.MISSING_DATA,
        message: `Missing "time" at index ${i}`,
        index: i,
        field: 'time',
        severity: 2,
      });
      hasIssue = true;
    }
    
    // Check for numeric value
    if (typeof point.value !== 'number' || isNaN(point.value)) {
      issues.push({
        type: ValidationErrorType.NON_NUMERIC_VALUE,
        message: `Non-numeric value at index ${i}: ${point.value}`,
        index: i,
        field: 'value',
        severity: 2,
      });
      hasIssue = true;
    }
    
    if (hasIssue) {
      pointsWithIssues++;
    }
  }
  
  // Calculate error percentage
  const errorPercentage = totalPoints > 0 ? (pointsWithIssues / totalPoints) * 100 : 0;
  
  return createValidationResult(issues, errorPercentage);
};

/**
 * Validates formatted histogram data
 * @param data Histogram data to validate
 * @returns Validation result
 */
export const validateHistogramData = (
  data: HistogramData[]
): ValidationResult => {
  const issues: ValidationIssue[] = [];
  
  // Check if data is defined
  if (!data) {
    issues.push({
      type: ValidationErrorType.MISSING_DATA,
      message: 'Data is undefined or null',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Check if array is empty
  if (data.length === 0) {
    issues.push({
      type: ValidationErrorType.EMPTY_DATA,
      message: 'Histogram data array is empty',
      severity: 3,
    });
    
    return createValidationResult(issues, 0);
  }
  
  // Track data points with issues for error percentage calculation
  let pointsWithIssues = 0;
  const totalPoints = data.length;
  
  // Validate each data point
  for (let i = 0; i < data.length; i++) {
    const point = data[i];
    let hasIssue = false;
    
    // Check for required properties
    if (!point.time) {
      issues.push({
        type: ValidationErrorType.MISSING_DATA,
        message: `Missing "time" at index ${i}`,
        index: i,
        field: 'time',
        severity: 2,
      });
      hasIssue = true;
    }
    
    // Check for numeric value
    if (typeof point.value !== 'number' || isNaN(point.value)) {
      issues.push({
        type: ValidationErrorType.NON_NUMERIC_VALUE,
        message: `Non-numeric value at index ${i}: ${point.value}`,
        index: i,
        field: 'value',
        severity: 2,
      });
      hasIssue = true;
    }
    
    if (hasIssue) {
      pointsWithIssues++;
    }
  }
  
  // Calculate error percentage
  const errorPercentage = totalPoints > 0 ? (pointsWithIssues / totalPoints) * 100 : 0;
  
  return createValidationResult(issues, errorPercentage);
};

/**
 * Attempts to fix common data issues
 * @param data OHLCV data to fix
 * @param validationResult Validation result with issues
 * @returns Fixed data and remaining issues
 */
export const fixOHLCVData = (
  data: OHLCVData,
  validationResult: ValidationResult
): { data: OHLCVData; remainingIssues: ValidationIssue[] } => {
  if (!data || !validationResult) {
    return { data, remainingIssues: validationResult?.issues || [] };
  }
  
  // Create a deep copy to avoid mutating the original
  const fixedData: OHLCVData = {
    dates: [...(data.dates || [])],
    ohlcv: [...(data.ohlcv || []).map(arr => [...arr])],
    metadata: data.metadata ? { ...data.metadata } : { symbol: '', timeframe: '', start: '', end: '', points: 0 }
  };
  
  // We can't fix array length mismatches, invalid types, etc.
  // Focus on fixing issues at the data point level
  
  // Group issues by index for efficient processing
  const issuesByIndex: { [index: number]: ValidationIssue[] } = {};
  
  for (const issue of validationResult.issues) {
    if (issue.index !== undefined) {
      if (!issuesByIndex[issue.index]) {
        issuesByIndex[issue.index] = [];
      }
      issuesByIndex[issue.index].push(issue);
    }
  }
  
  // Process each point with issues
  for (const indexStr in issuesByIndex) {
    const index = parseInt(indexStr, 10);
    const issues = issuesByIndex[index];
    
    // Skip if index is out of bounds
    if (index < 0 || index >= fixedData.ohlcv.length) {
      continue;
    }
    
    const ohlcv = fixedData.ohlcv[index];
    
    // Fix non-numeric values
    for (const issue of issues) {
      if (issue.type === ValidationErrorType.NON_NUMERIC_VALUE && issue.field) {
        const fieldIndices: Record<string, number> = {
          open: 0,
          high: 1,
          low: 2,
          close: 3,
          volume: 4
        };
        
        if (fieldIndices[issue.field] !== undefined) {
          const fieldIndex = fieldIndices[issue.field];
          
          // Use previous value if available, otherwise use 0
          if (index > 0) {
            ohlcv[fieldIndex] = fixedData.ohlcv[index - 1][fieldIndex];
          } else {
            ohlcv[fieldIndex] = 0;
          }
        }
      }
    }
    
    // Fix invalid OHLC relationships
    let [open, high, low, close, volume] = ohlcv;
    
    // Make sure high is the highest value
    high = Math.max(open, high, low, close);
    
    // Make sure low is the lowest value
    low = Math.min(open, low, close);
    
    // Fix negative volume
    if (volume < 0) {
      volume = 0;
    }
    
    // Update the fixed data with corrected values
    fixedData.ohlcv[index] = [open, high, low, close, volume];
  }
  
  // Fix metadata issues
  if (fixedData.metadata) {
    if (!fixedData.metadata.symbol) {
      fixedData.metadata.symbol = 'UNKNOWN';
    }
    
    if (!fixedData.metadata.timeframe) {
      fixedData.metadata.timeframe = '1d';
    }
    
    if (fixedData.metadata.points !== fixedData.dates.length) {
      fixedData.metadata.points = fixedData.dates.length;
    }
    
    if (!fixedData.metadata.start && fixedData.dates.length > 0) {
      fixedData.metadata.start = fixedData.dates[0].toString();
    }
    
    if (!fixedData.metadata.end && fixedData.dates.length > 0) {
      fixedData.metadata.end = fixedData.dates[fixedData.dates.length - 1].toString();
    }
  }
  
  // Determine remaining issues
  const remainingIssues = validationResult.issues.filter(issue => {
    // We can't fix these types of issues
    return [
      ValidationErrorType.MISSING_DATA,
      ValidationErrorType.INVALID_TYPE,
      ValidationErrorType.ARRAY_LENGTH_MISMATCH,
      ValidationErrorType.EMPTY_DATA
    ].includes(issue.type);
  });
  
  return { data: fixedData, remainingIssues };
};

/**
 * Creates a validation result object
 * @param issues List of validation issues
 * @param errorPercentage Percentage of data points with issues
 * @returns Validation result
 */
function createValidationResult(issues: ValidationIssue[], errorPercentage: number): ValidationResult {
  // Build summary by type
  const summary: { [key in ValidationErrorType]?: number } = {};
  
  for (const issue of issues) {
    summary[issue.type] = (summary[issue.type] || 0) + 1;
  }
  
  // Determine if rendering should be prevented
  const preventRendering = issues.some(issue => issue.severity === 3) || 
                          errorPercentage > DEFAULT_VALIDATION_OPTIONS.maxErrorPercentage!;
  
  return {
    valid: issues.length === 0,
    issues,
    summary,
    errorPercentage,
    preventRendering
  };
}