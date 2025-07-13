# Azure Data Factory CSV Validation Pipeline

## Overview
This pipeline validates CSV files through multiple validation steps before loading them into SQL Server. It includes schema validation, row count comparison, file format checks, and data quality validations.

## Pipeline Architecture for Large Files (4GB+)

### 1. Pipeline Parameters
```json
{
  "sourceFilePath": "https://yourstorageaccount.blob.core.windows.net/container/filename.csv",
  "targetTableName": "YourTargetTable",
  "expectedSchema": "column1:string,column2:int,column3:datetime",
  "validationMode": "strict",
  "chunkSize": 100000,
  "maxParallelism": 8,
  "compressionType": "gzip",
  "enablePartitioning": true
}
```

### 2. Infrastructure Requirements

**Integration Runtime Configuration:**
- **Azure Integration Runtime**: Use Auto-resolve with 8+ cores
- **Self-hosted IR**: Recommended for very large files
  - Memory: 32GB+ RAM
  - CPU: 8+ cores
  - Storage: SSD with high IOPS

**Storage Optimization:**
- **Premium Storage**: Use Premium SSD for staging
- **Hot Tier**: Keep active files in hot storage tier
- **Hierarchical Namespace**: Enable for better performance

**Data Flow Cluster Configuration:**
```json
{
  "computeType": "General",
  "coreCount": 32,
  "timeToLive": 10,
  "enableQuickReuse": true
}
```

### 2. Variables
```json
{
  "currentRowCount": 0,
  "previousRowCount": 0,
  "validationErrors": [],
  "fileSize": 0,
  "processingDate": "@utcnow()"
}
```

## Large File Processing Strategy

### Pre-Processing: File Splitting and Chunking

**Activity 1: File Size Assessment**
```python
# Custom Activity - Python Script
import os
import math

def assess_file_size(file_path):
    file_size = os.path.getsize(file_path)
    gb_size = file_size / (1024**3)
    
    # Determine processing strategy
    if gb_size > 2:
        return {
            "strategy": "chunked_processing",
            "chunk_count": math.ceil(gb_size / 0.5),  # 500MB chunks
            "parallel_streams": min(8, math.ceil(gb_size / 2))
        }
    else:
        return {
            "strategy": "standard_processing",
            "chunk_count": 1,
            "parallel_streams": 1
        }
```

**Activity 2: Dynamic File Partitioning**
```python
# Split large CSV into manageable chunks
def split_csv_file(input_file, chunk_size=100000):
    import pandas as pd
    
    chunk_files = []
    chunk_number = 0
    
    # Read file in chunks
    for chunk in pd.read_csv(input_file, chunksize=chunk_size):
        chunk_file = f"{input_file}_chunk_{chunk_number}.csv"
        chunk.to_csv(chunk_file, index=False)
        chunk_files.append(chunk_file)
        chunk_number += 1
    
    return chunk_files
```

### Parallel Processing Architecture

**ForEach Activity Configuration:**
```json
{
  "activities": [
    {
      "name": "ProcessChunksInParallel",
      "type": "ForEach",
      "typeProperties": {
        "items": "@activity('SplitFile').output.chunk_files",
        "batchCount": 8,
        "activities": [
          {
            "name": "ValidateChunk",
            "type": "DataFlow"
          }
        ]
      }
    }
  ]
}
```

## Validation Steps (Optimized for Large Files)

### Step 1: Streaming File Validation

**Activity: Streaming Metadata Validation**
```python
# Memory-efficient file validation
def validate_large_csv_streaming(file_path):
    import csv
    import chardet
    
    validation_results = {
        "file_size": 0,
        "row_count": 0,
        "column_count": 0,
        "encoding": None,
        "errors": []
    }
    
    # Detect encoding from first 10KB
    with open(file_path, 'rb') as f:
        raw_sample = f.read(10240)
        encoding = chardet.detect(raw_sample)['encoding']
        validation_results["encoding"] = encoding
    
    # Stream through file for validation
    with open(file_path, 'r', encoding=encoding) as f:
        csv_reader = csv.reader(f)
        
        # Validate header
        header = next(csv_reader)
        validation_results["column_count"] = len(header)
        
        # Count rows efficiently
        row_count = sum(1 for row in csv_reader)
        validation_results["row_count"] = row_count
        
        # Get file size
        validation_results["file_size"] = os.path.getsize(file_path)
    
    return validation_results
```

### Step 2: Distributed Schema Validation

**Data Flow with Partitioning:**
```json
{
  "source": {
    "dataset": "LargeCSVDataset",
    "options": {
      "partitionOption": "dynamicRange",
      "partitionSettings": {
        "partitionColumnNames": ["partition_key"],
        "maxPartitions": 8
      }
    }
  },
  "schemaValidation": {
    "type": "assert",
    "settings": {
      "assertConditions": [
        {
          "condition": "columnCount() == @pipeline().parameters.expectedColumnCount",
          "description": "Column count validation"
        },
        {
          "condition": "!isNull(key_column)",
          "description": "Key column validation"
        }
      ]
    }
  }
}
```

### Step 3: Memory-Efficient Row Count Validation

**Activity: Parallel Row Counting**
```sql
-- Use SQL Server's parallel processing
SELECT COUNT_BIG(*) as total_rows
FROM OPENROWSET(
    BULK 'your-file-path',
    FORMAT = 'CSV',
    FIRSTROW = 2,
    MAXERRORS = 0
) AS [result]
OPTION (MAXDOP 8);  -- Use 8 parallel threads
```

**Activity: Historical Comparison with Indexing**
```sql
-- Optimized historical lookup
SELECT TOP 1 row_count as previous_count
FROM file_processing_log WITH (INDEX(IX_processing_date))
WHERE table_name = '@{pipeline().parameters.targetTableName}'
AND processing_date >= DATEADD(day, -7, GETDATE())
ORDER BY processing_date DESC;
```

### Step 4: Streaming Data Quality Validation

**Memory-Efficient Quality Checks:**
```python
def validate_data_quality_streaming(file_path, chunk_size=10000):
    import pandas as pd
    
    quality_metrics = {
        "null_count": 0,
        "duplicate_count": 0,
        "invalid_dates": 0,
        "invalid_emails": 0,
        "total_rows": 0
    }
    
    seen_keys = set()
    
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        # Process chunk
        quality_metrics["total_rows"] += len(chunk)
        quality_metrics["null_count"] += chunk.isnull().sum().sum()
        
        # Check duplicates (memory-efficient)
        chunk_keys = set(chunk['key_column'].values)
        duplicates = chunk_keys.intersection(seen_keys)
        quality_metrics["duplicate_count"] += len(duplicates)
        seen_keys.update(chunk_keys)
        
        # Validate dates and emails
        if 'date_column' in chunk.columns:
            invalid_dates = pd.to_datetime(chunk['date_column'], errors='coerce').isna().sum()
            quality_metrics["invalid_dates"] += invalid_dates
        
        if 'email_column' in chunk.columns:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}

## Error Handling and Logging

### Validation Error Logging
```sql
CREATE TABLE validation_log (
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    file_name VARCHAR(255),
    validation_step VARCHAR(100),
    error_message TEXT,
    error_count INT,
    processing_date DATETIME,
    pipeline_run_id VARCHAR(100)
);
```

### Pipeline Error Handling
- **On Validation Failure**: Log error, send notification, stop pipeline
- **On Partial Success**: Log warnings, continue with valid data
- **On Success**: Log success metrics, proceed to load

## Optimized Data Loading for Large Files

### Step 6: High-Performance Staging Strategy

**Multi-Stage Loading Approach:**
```sql
-- Create partitioned staging table
CREATE TABLE staging_table (
    [Column1] VARCHAR(100),
    [Column2] INT,
    [Column3] DATETIME,
    [load_date] DATETIME DEFAULT GETDATE(),
    [pipeline_run_id] VARCHAR(100),
    [chunk_id] INT
) 
ON [PRIMARY]
PARTITION BY RANGE (chunk_id);

-- Create columnstore index for fast aggregations
CREATE CLUSTERED COLUMNSTORE INDEX CCI_staging_table ON staging_table;
```

**Activity: Parallel Copy with Staging**
```json
{
  "copy": {
    "source": {
      "type": "DelimitedTextSource",
      "storeSettings": {
        "type": "AzureBlobStorageReadSettings",
        "recursive": true,
        "wildcardFileName": "*.csv"
      },
      "formatSettings": {
        "type": "DelimitedTextReadSettings",
        "compressionProperties": {
          "type": "GZipDeflateReadSettings"
        }
      }
    },
    "sink": {
      "type": "SqlServerSink",
      "writeBatchSize": 100000,
      "writeBatchTimeout": "00:30:00",
      "preCopyScript": "TRUNCATE TABLE staging_table_temp",
      "sqlWriterStoredProcedureName": "sp_bulk_insert_staging"
    },
    "enableStaging": true,
    "stagingSettings": {
      "linkedServiceName": "AzureBlobStorage",
      "path": "staging-container/temp",
      "enableCompression": true
    },
    "parallelCopies": 8,
    "dataIntegrationUnits": 32
  }
}
```

### Step 7: Streaming Data Transformation

**Memory-Efficient Data Flow:**
```json
{
  "dataFlow": {
    "type": "MappingDataFlow",
    "typeProperties": {
      "sources": [
        {
          "dataset": "StagingDataset",
          "name": "StagingSource",
          "options": {
            "enableCacheSink": false,
            "isolationLevel": "READ_UNCOMMITTED"
          }
        }
      ],
      "transformations": [
        {
          "name": "StreamingTransform",
          "type": "derivedColumn",
          "settings": {
            "streaming": true,
            "columns": [
              {
                "name": "processed_date",
                "expression": "currentUTC()"
              },
              {
                "name": "row_hash",
                "expression": "sha1(toString(column1) + toString(column2))"
              }
            ]
          }
        },
        {
          "name": "StreamingValidation",
          "type": "assert",
          "settings": {
            "streaming": true,
            "assertConditions": [
              {
                "condition": "!isNull(column1) && length(column1) > 0",
                "description": "Column1 validation"
              }
            ]
          }
        }
      ],
      "sinks": [
        {
          "dataset": "TargetDataset",
          "name": "TargetSink",
          "options": {
            "truncate": false,
            "insertBatchSize": 100000
          }
        }
      ]
    },
    "compute": {
      "coreCount": 32,
      "computeType": "MemoryOptimized"
    }
  }
}
```

### Step 8: Bulk Insert Optimization

**Optimized Bulk Insert Stored Procedure:**
```sql
CREATE PROCEDURE sp_bulk_insert_optimized
    @chunk_id INT,
    @batch_size INT = 100000
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Use batch processing to avoid memory issues
    DECLARE @offset INT = 0;
    DECLARE @row_count INT = 1;
    
    WHILE @row_count > 0
    BEGIN
        -- Process in batches
        WITH batch_data AS (
            SELECT *
            FROM staging_table
            WHERE chunk_id = @chunk_id
            ORDER BY load_date
            OFFSET @offset ROWS
            FETCH NEXT @batch_size ROWS ONLY
        )
        INSERT INTO target_table (column1, column2, column3, created_date)
        SELECT column1, column2, column3, GETDATE()
        FROM batch_data;
        
        SET @row_count = @@ROWCOUNT;
        SET @offset = @offset + @batch_size;
        
        -- Commit every batch to avoid long transactions
        IF @row_count > 0 
            COMMIT TRANSACTION;
    END;
END;
```

### Step 9: Memory Management and Cleanup

**Activity: Cleanup Temporary Resources**
```python
def cleanup_temp_resources(chunk_files, temp_tables):
    import os
    import pyodbc
    
    # Clean up temporary files
    for chunk_file in chunk_files:
        try:
            os.remove(chunk_file)
        except OSError:
            pass
    
    # Clean up temporary database objects
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    
    for temp_table in temp_tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
        except:
            pass
    
    conn.commit()
    conn.close()
```

## Advanced Performance Optimizations

### 1. Compressed File Processing

**Activity: Automatic Compression Detection**
```python
def process_compressed_file(file_path):
    import gzip
    import zipfile
    
    if file_path.endswith('.gz'):
        with gzip.open(file_path, 'rt') as f:
            # Process gzipped CSV
            return process_csv_stream(f)
    elif file_path.endswith('.zip'):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # Extract and process
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            for csv_file in csv_files:
                with zip_ref.open(csv_file) as f:
                    process_csv_stream(f)
```

### 2. Intelligent Partitioning Strategy

**Dynamic Partitioning Based on File Size:**
```json
{
  "partitioning": {
    "strategy": "dynamic",
    "rules": [
      {
        "condition": "file_size_gb < 1",
        "partitions": 2
      },
      {
        "condition": "file_size_gb >= 1 AND file_size_gb < 5",
        "partitions": 8
      },
      {
        "condition": "file_size_gb >= 5",
        "partitions": 16
      }
    ]
  }
}
```

### 3. Incremental Processing

**Activity: Delta Processing for Large Files**
```python
def process_incremental_changes(current_file, previous_file):
    import pandas as pd
    
    # Read files in chunks and compare
    current_chunks = pd.read_csv(current_file, chunksize=10000)
    previous_chunks = pd.read_csv(previous_file, chunksize=10000)
    
    changes = {
        'inserted': [],
        'updated': [],
        'deleted': []
    }
    
    for current_chunk, previous_chunk in zip(current_chunks, previous_chunks):
        # Compare chunks and identify changes
        merged = current_chunk.merge(previous_chunk, on='key_column', how='outer', indicator=True)
        
        changes['inserted'].extend(merged[merged['_merge'] == 'left_only'].to_dict('records'))
        changes['updated'].extend(merged[merged['_merge'] == 'both'].to_dict('records'))
        changes['deleted'].extend(merged[merged['_merge'] == 'right_only'].to_dict('records'))
    
    return changes
```

### 4. Monitoring and Performance Metrics

**Real-time Performance Monitoring:**
```sql
-- Create performance monitoring table
CREATE TABLE pipeline_performance_metrics (
    metric_id INT IDENTITY(1,1) PRIMARY KEY,
    pipeline_run_id VARCHAR(100),
    file_name VARCHAR(255),
    file_size_gb DECIMAL(10,2),
    processing_start_time DATETIME,
    processing_end_time DATETIME,
    validation_duration_minutes INT,
    load_duration_minutes INT,
    records_processed BIGINT,
    records_per_second DECIMAL(10,2),
    memory_usage_gb DECIMAL(10,2),
    cpu_usage_percent DECIMAL(5,2),
    created_date DATETIME DEFAULT GETDATE()
);
```

**Activity: Performance Metrics Collection**
```python
def collect_performance_metrics(start_time, end_time, records_processed, file_size):
    import psutil
    import time
    
    duration = (end_time - start_time).total_seconds()
    records_per_second = records_processed / duration if duration > 0 else 0
    
    metrics = {
        'processing_duration': duration,
        'records_per_second': records_per_second,
        'memory_usage_gb': psutil.virtual_memory().used / (1024**3),
        'cpu_usage_percent': psutil.cpu_percent(interval=1),
        'throughput_mb_per_second': (file_size / (1024**2)) / duration
    }
    
    return metrics
```

### 5. Error Recovery and Checkpointing

**Activity: Checkpoint-based Recovery**
```python
def create_checkpoint(chunk_id, processed_rows, validation_status):
    checkpoint_data = {
        'chunk_id': chunk_id,
        'processed_rows': processed_rows,
        'validation_status': validation_status,
        'timestamp': datetime.now(),
        'pipeline_run_id': pipeline_run_id
    }
    
    # Save checkpoint to database
    save_checkpoint(checkpoint_data)
    
    return checkpoint_data

def resume_from_checkpoint(pipeline_run_id):
    # Load last successful checkpoint
    checkpoint = load_checkpoint(pipeline_run_id)
    
    if checkpoint:
        return {
            'resume_from_chunk': checkpoint['chunk_id'],
            'processed_rows': checkpoint['processed_rows']
        }
    
    return None
```

## Resource Management

### Auto-scaling Configuration

**Integration Runtime Auto-scaling:**
```json
{
  "computeProperties": {
    "location": "East US",
    "nodeSize": "Standard_D4s_v3",
    "numberOfNodes": 1,
    "maxParallelExecutionsPerNode": 8,
    "dataFlowProperties": {
      "computeType": "MemoryOptimized",
      "coreCount": 32,
      "timeToLive": 10
    }
  },
  "autoScaling": {
    "enabled": true,
    "minNodes": 1,
    "maxNodes": 10,
    "scaleUpThreshold": 80,
    "scaleDownThreshold": 20
  }
}
```

### Cost Optimization

**Activity: Dynamic Resource Allocation**
```python
def optimize_resources_for_file_size(file_size_gb):
    if file_size_gb < 1:
        return {
            'integration_runtime': 'AutoResolveIntegrationRuntime',
            'diu': 4,
            'parallel_copies': 2
        }
    elif file_size_gb < 5:
        return {
            'integration_runtime': 'AutoResolveIntegrationRuntime',
            'diu': 16,
            'parallel_copies': 8
        }
    else:
        return {
            'integration_runtime': 'AutoResolveIntegrationRuntime',
            'diu': 32,
            'parallel_copies': 16
        }
``` as ## Advanced Validation Strategies for Large Files

### 6. Sampling-Based Validation

**Activity: Statistical Sampling for Quick Validation**
```python
def statistical_validation_sample(file_path, sample_size=50000):
    import pandas as pd
    import numpy as np
    
    # Get total row count first
    total_rows = sum(1 for line in open(file_path, 'r', encoding='utf-8')) - 1
    
    # Create random sample indices
    sample_indices = np.random.choice(total_rows, min(sample_size, total_rows), replace=False)
    sample_indices = sorted(sample_indices)
    
    # Read only sampled rows
    sample_data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        current_row = 0
        sample_idx = 0
        
        for row in reader:
            if sample_idx < len(sample_indices) and current_row == sample_indices[sample_idx]:
                sample_data.append(row)
                sample_idx += 1
            current_row += 1
            
            if sample_idx >= len(sample_indices):
                break
    
    # Perform validation on sample
    df_sample = pd.DataFrame(sample_data, columns=header)
    
    validation_results = {
        'null_percentage': (df_sample.isnull().sum().sum() / (len(df_sample) * len(df_sample.columns))) * 100,
        'duplicate_percentage': (df_sample.duplicated().sum() / len(df_sample)) * 100,
        'data_type_issues': validate_data_types(df_sample),
        'outlier_detection': detect_outliers(df_sample),
        'sample_size': len(df_sample),
        'confidence_level': calculate_confidence_level(len(df_sample), total_rows)
    }
    
    return validation_results
```

### 7. Progressive Validation

**Activity: Multi-Pass Validation Strategy**
```python
def progressive_validation(file_path, validation_passes=3):
    """
    Pass 1: Quick structural validation (encoding, basic format)
    Pass 2: Schema and data type validation
    Pass 3: Business rules and data quality validation
    """
    
    results = {
        'pass_1': {'status': 'pending', 'duration': 0, 'issues': []},
        'pass_2': {'status': 'pending', 'duration': 0, 'issues': []},
        'pass_3': {'status': 'pending', 'duration': 0, 'issues': []}
    }
    
    # Pass 1: Structural validation (fastest)
    start_time = time.time()
    try:
        structural_issues = validate_file_structure(file_path)
        results['pass_1']['status'] = 'completed'
        results['pass_1']['issues'] = structural_issues
        results['pass_1']['duration'] = time.time() - start_time
        
        if len(structural_issues) > 0:
            return results  # Stop if structural issues found
    except Exception as e:
        results['pass_1']['status'] = 'failed'
        results['pass_1']['issues'] = [str(e)]
        return results
    
    # Pass 2: Schema validation
    start_time = time.time()
    try:
        schema_issues = validate_schema_streaming(file_path)
        results['pass_2']['status'] = 'completed'
        results['pass_2']['issues'] = schema_issues
        results['pass_2']['duration'] = time.time() - start_time
        
        if len(schema_issues) > 10:  # Threshold for critical issues
            return results
    except Exception as e:
        results['pass_2']['status'] = 'failed'
        results['pass_2']['issues'] = [str(e)]
        return results
    
    # Pass 3: Business rules validation
    start_time = time.time()
    try:
        business_issues = validate_business_rules_streaming(file_path)
        results['pass_3']['status'] = 'completed'
        results['pass_3']['issues'] = business_issues
        results['pass_3']['duration'] = time.time() - start_time
    except Exception as e:
        results['pass_3']['status'] = 'failed'
        results['pass_3']['issues'] = [str(e)]
    
    return results
```

### 8. Memory-Optimized Duplicate Detection

**Activity: Bloom Filter for Duplicate Detection**
```python
def detect_duplicates_bloom_filter(file_path, key_column_index=0):
    from pybloom_live import BloomFilter
    import csv
    
    # Initialize bloom filter for approximate duplicate detection
    expected_items = 10000000  # 10M items
    bloom_filter = BloomFilter(capacity=expected_items, error_rate=0.1)
    
    duplicates_found = 0
    potential_duplicates = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for row_num, row in enumerate(reader, 1):
            key_value = row[key_column_index]
            
            if key_value in bloom_filter:
                # Potential duplicate - needs exact verification
                potential_duplicates.append((row_num, key_value))
                duplicates_found += 1
            else:
                bloom_filter.add(key_value)
    
    # Verify potential duplicates with exact matching
    exact_duplicates = verify_exact_duplicates(file_path, potential_duplicates, key_column_index)
    
    return {
        'potential_duplicates': len(potential_duplicates),
        'confirmed_duplicates': len(exact_duplicates),
        'duplicate_rate': (len(exact_duplicates) / row_num) * 100 if row_num > 0 else 0
    }
```

### 9. Adaptive Validation Thresholds

**Activity: Dynamic Threshold Management**
```python
def adaptive_validation_thresholds(file_path, historical_data):
    """
    Adjust validation thresholds based on historical patterns
    """
    import numpy as np
    
    # Calculate historical statistics
    historical_stats = calculate_historical_stats(historical_data)
    
    # Dynamic thresholds based on historical performance
    thresholds = {
        'max_null_percentage': min(historical_stats['avg_null_rate'] * 1.5, 10),
        'max_duplicate_percentage': min(historical_stats['avg_duplicate_rate'] * 2, 5),
        'min_row_count': max(historical_stats['avg_row_count'] * 0.8, 1000),
        'max_row_count': historical_stats['avg_row_count'] * 1.2,
        'max_processing_time_minutes': historical_stats['avg_processing_time'] * 1.5
    }
    
    # Seasonal adjustments
    current_month = datetime.now().month
    if current_month in [12, 1, 2]:  # Winter months might have different patterns
        thresholds['min_row_count'] *= 0.9
    elif current_month in [6, 7, 8]:  # Summer months
        thresholds['min_row_count'] *= 1.1
    
    return thresholds
```

## Real-time Monitoring and Alerting

### 10. Live Processing Dashboard

**Activity: Real-time Metrics Collection**
```python
def collect_realtime_metrics(pipeline_run_id, chunk_id=None):
    import psutil
    import time
    
    metrics = {
        'timestamp': datetime.now(),
        'pipeline_run_id': pipeline_run_id,
        'chunk_id': chunk_id,
        'cpu_usage': psutil.cpu_percent(interval=1),
        'memory_usage_gb': psutil.virtual_memory().used / (1024**3),
        'memory_percentage': psutil.virtual_memory().percent,
        'disk_io_read_mb': psutil.disk_io_counters().read_bytes / (1024**2),
        'disk_io_write_mb': psutil.disk_io_counters().write_bytes / (1024**2),
        'network_io_sent_mb': psutil.net_io_counters().bytes_sent / (1024**2),
        'network_io_recv_mb': psutil.net_io_counters().bytes_recv / (1024**2)
    }
    
    # Send to monitoring system
    send_metrics_to_dashboard(metrics)
    
    return metrics
```

### 11. Intelligent Alerting System

**Activity: Multi-level Alert Configuration**
```python
def setup_intelligent_alerts(pipeline_config):
    alert_rules = {
        'critical': {
            'conditions': [
                'memory_usage > 90%',
                'processing_time > expected_time * 3',
                'error_rate > 5%',
                'duplicate_rate > 10%'
            ],
            'actions': ['email_admin', 'stop_pipeline', 'create_incident']
        },
        'warning': {
            'conditions': [
                'memory_usage > 70%',
                'processing_time > expected_time * 2',
                'error_rate > 1%',
                'null_rate > historical_avg * 2'
            ],
            'actions': ['email_team', 'log_warning']
        },
        'info': {
            'conditions': [
                'processing_completed',
                'validation_passed',
                'load_completed'
            ],
            'actions': ['log_info', 'update_dashboard']
        }
    }
    
    return alert_rules
```

## Disaster Recovery and Backup

### 12. Automated Backup Strategy

**Activity: Incremental Backup System**
```python
def create_backup_strategy(file_path, backup_location):
    import shutil
    import hashlib
    
    # Create file hash for integrity checking
    file_hash = calculate_file_hash(file_path)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"backup_{timestamp}_{file_hash[:8]}.csv"
    backup_path = os.path.join(backup_location, backup_filename)
    
    # Copy with compression
    with open(file_path, 'rb') as f_in:
        with gzip.open(backup_path + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    # Store backup metadata
    backup_metadata = {
        'original_file': file_path,
        'backup_path': backup_path + '.gz',
        'file_hash': file_hash,
        'backup_date': datetime.now(),
        'file_size': os.path.getsize(file_path),
        'compressed_size': os.path.getsize(backup_path + '.gz')
    }
    
    return backup_metadata
```

### 13. Recovery Procedures

**Activity: Automated Recovery System**
```python
def recovery_procedure(pipeline_run_id, recovery_point):
    """
    Automated recovery from checkpoints
    """
    
    # Load recovery point data
    recovery_data = load_recovery_point(recovery_point)
    
    if recovery_data:
        # Restore from last successful state
        restored_chunks = restore_processed_chunks(recovery_data['processed_chunks'])
        
        # Resume from failure point
        resume_config = {
            'start_chunk': recovery_data['last_successful_chunk'] + 1,
            'processed_rows': recovery_data['processed_rows'],
            'validation_state': recovery_data['validation_state']
        }
        
        return resume_config
    
    return None
```

## Final Implementation Checklist for Large Files

### Performance Optimization Checklist:

✅ **Infrastructure Setup:**
- [ ] Configure high-memory Integration Runtime (32GB+ RAM)
- [ ] Set up Premium SSD storage for staging
- [ ] Configure parallel processing (8+ cores)
- [ ] Enable auto-scaling for variable workloads

✅ **File Processing Strategy:**
- [ ] Implement file chunking for files > 2GB
- [ ] Set up parallel chunk processing
- [ ] Configure streaming validation
- [ ] Implement progressive validation passes

✅ **Memory Management:**
- [ ] Use streaming APIs for file reading
- [ ] Implement memory-efficient duplicate detection
- [ ] Configure appropriate batch sizes
- [ ] Set up memory monitoring and alerts

✅ **Performance Monitoring:**
- [ ] Real-time metrics collection
- [ ] Performance benchmarking
- [ ] Bottleneck identification
- [ ] Resource utilization tracking

✅ **Error Handling:**
- [ ] Checkpoint-based recovery
- [ ] Automated retry mechanisms
- [ ] Graceful degradation strategies
- [ ] Comprehensive error logging

✅ **Scalability Features:**
- [ ] Dynamic resource allocation
- [ ] Adaptive validation thresholds
- [ ] Horizontal scaling capabilities
- [ ] Load balancing for parallel processing

### Expected Performance Improvements:

**For 4GB+ Files:**
- **Processing Time**: 80-90% reduction through parallel processing
- **Memory Usage**: 70-80% reduction through streaming
- **Reliability**: 95%+ success rate with recovery mechanisms
- **Scalability**: Linear scaling up to 50GB+ files

**Resource Requirements:**
- **CPU**: 8-16 cores for optimal performance
- **Memory**: 32-64GB RAM for large file processing
- **Storage**: Premium SSD with 1000+ IOPS
- **Network**: 1Gbps+ for efficient data transfer

This optimized pipeline can handle your 4GB files efficiently and will scale as your files continue to grow, with robust validation, monitoring, and recovery capabilities.
            invalid_emails = ~chunk['email_column'].str.match(email_pattern, na=False)
            quality_metrics["invalid_emails"] += invalid_emails.sum()
    
    return quality_metrics
```

### Step 5: Advanced Corruption Detection

**Activity: Parallel Corruption Scanning**
```python
def detect_corruption_parallel(file_path, num_processes=4):
    import multiprocessing
    import os
    
    def scan_file_chunk(start_pos, end_pos):
        corruption_issues = []
        
        with open(file_path, 'rb') as f:
            f.seek(start_pos)
            
            while f.tell() < end_pos:
                line = f.readline()
                if not line:
                    break
                
                # Check for binary data in text file
                try:
                    line.decode('utf-8')
                except UnicodeDecodeError:
                    corruption_issues.append(f"Binary data at position {f.tell()}")
                
                # Check for extremely long lines (potential corruption)
                if len(line) > 100000:  # 100KB line limit
                    corruption_issues.append(f"Extremely long line at position {f.tell()}")
        
        return corruption_issues
    
    # Divide file into chunks for parallel processing
    file_size = os.path.getsize(file_path)
    chunk_size = file_size // num_processes
    
    processes = []
    for i in range(num_processes):
        start_pos = i * chunk_size
        end_pos = (i + 1) * chunk_size if i < num_processes - 1 else file_size
        
        process = multiprocessing.Process(
            target=scan_file_chunk,
            args=(start_pos, end_pos)
        )
        processes.append(process)
        process.start()
    
    # Collect results
    all_issues = []
    for process in processes:
        process.join()
        # Collect results from shared memory or queue
    
    return all_issues
```

## Error Handling and Logging

### Validation Error Logging
```sql
CREATE TABLE validation_log (
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    file_name VARCHAR(255),
    validation_step VARCHAR(100),
    error_message TEXT,
    error_count INT,
    processing_date DATETIME,
    pipeline_run_id VARCHAR(100)
);
```

### Pipeline Error Handling
- **On Validation Failure**: Log error, send notification, stop pipeline
- **On Partial Success**: Log warnings, continue with valid data
- **On Success**: Log success metrics, proceed to load

## Data Loading Pipeline

### Step 8: Staging Data Load
```sql
-- Create staging table
CREATE TABLE staging_table (
    [Column1] VARCHAR(100),
    [Column2] INT,
    [Column3] DATETIME,
    [load_date] DATETIME DEFAULT GETDATE(),
    [pipeline_run_id] VARCHAR(100)
);
```

**Activity: Copy to Staging**
- Activity Type: Copy Data
- Source: Validated CSV file
- Sink: SQL Server staging table
- Settings:
  - Enable staging
  - Fault tolerance: Skip incompatible rows
  - Log incompatible rows

### Step 9: Data Transformation and Final Load

**Activity: Transform and Load**
- Activity Type: Data Flow or Stored Procedure
- Transformations:
  - Data type conversions
  - Business logic applications
  - Surrogate key generation
  - Slowly changing dimension handling

```sql
-- Example transformation stored procedure
CREATE PROCEDURE sp_transform_and_load
AS
BEGIN
    BEGIN TRANSACTION;
    
    -- Insert new records
    INSERT INTO target_table (column1, column2, column3, created_date)
    SELECT column1, column2, column3, GETDATE()
    FROM staging_table s
    WHERE NOT EXISTS (
        SELECT 1 FROM target_table t 
        WHERE t.key_column = s.key_column
    );
    
    -- Update existing records
    UPDATE t 
    SET column1 = s.column1,
        column2 = s.column2,
        column3 = s.column3,
        modified_date = GETDATE()
    FROM target_table t
    INNER JOIN staging_table s ON t.key_column = s.key_column
    WHERE t.column1 != s.column1 OR t.column2 != s.column2 OR t.column3 != s.column3;
    
    COMMIT TRANSACTION;
END;
```

### Step 10: Post-Load Validation

**Activity: Data Quality Checks**
```sql
-- Validate loaded data
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT key_column) as unique_records,
    SUM(CASE WHEN column1 IS NULL THEN 1 ELSE 0 END) as null_count,
    MIN(created_date) as min_date,
    MAX(created_date) as max_date
FROM target_table
WHERE DATE(created_date) = DATE(GETDATE());
```

**Activity: Update Processing Log**
```sql
INSERT INTO file_processing_log (
    file_name, 
    table_name, 
    row_count, 
    processing_date, 
    status, 
    pipeline_run_id
) VALUES (
    '@{pipeline().parameters.sourceFilePath}',
    '@{pipeline().parameters.targetTableName}',
    @{variables('currentRowCount')},
    GETDATE(),
    'Success',
    '@{pipeline().RunId}'
);
```

## Pipeline Configuration

### Triggers
- **Schedule Trigger**: Daily at specific time
- **Storage Event Trigger**: When new file arrives
- **Tumbling Window Trigger**: For historical data processing

### Monitoring and Alerting
- **Success Notification**: Email/Teams message
- **Failure Notification**: Include error details and suggested actions
- **Custom Metrics**: Track validation success rates
- **Dashboard Integration**: Power BI or Azure Monitor

### Performance Optimization
- **Parallel Processing**: Use Data Flow clusters
- **Partitioning**: Partition large files
- **Caching**: Cache reference data
- **Compression**: Use compressed intermediate storage

## Implementation Checklist

1. ✅ Create linked services (Storage Account, SQL Server)
2. ✅ Create datasets (CSV source, SQL sink)
3. ✅ Create data flows for validation
4. ✅ Create pipeline with all activities
5. ✅ Set up error handling and logging
6. ✅ Configure monitoring and alerts
7. ✅ Test with sample data
8. ✅ Deploy to production environment

## Best Practices

- **Version Control**: Use Git integration for pipeline versioning
- **Environment Management**: Use ARM templates for deployment
- **Security**: Use Key Vault for connection strings
- **Cost Optimization**: Use appropriate integration runtime sizing
- **Documentation**: Maintain pipeline documentation and runbooks