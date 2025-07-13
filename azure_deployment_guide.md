# Step-by-Step Azure Deployment Guide for CSV Validation Pipeline

## Prerequisites

### 1. Azure Account Setup
- **Create Azure Account**: Go to [portal.azure.com](https://portal.azure.com) and sign up for a free account
- **Free Tier**: You get $200 credit for 30 days and many services free for 12 months
- **Subscription**: Once signed up, you'll have a default subscription

### 2. Required Permissions
- You need **Contributor** or **Owner** role on the subscription
- This is automatically granted if you created the subscription

## Step 1: Access Azure Portal

1. Navigate to [portal.azure.com](https://portal.azure.com)
2. Sign in with your Azure credentials
3. You should see the Azure dashboard

## Step 2: Create Resource Group

A resource group is a container that holds related resources.

1. **Click** "Resource groups" in the left sidebar
2. **Click** "+ Create" at the top
3. **Fill in the details**:
   - **Subscription**: Select your subscription
   - **Resource group name**: `csv-validation-rg`
   - **Region**: Choose a region close to you (e.g., East US, West Europe)
4. **Click** "Review + create"
5. **Click** "Create"

## Step 3: Deploy the ARM Template

### Method 1: Using Azure Portal (Recommended for beginners)

1. **Click** "Create a resource" (+ icon) in the top left
2. **Search** for "Template deployment"
3. **Select** "Template deployment (deploy using custom templates)"
4. **Click** "Create"
5. **Select** "Build your own template in the editor"
6. **Delete** the existing content in the editor
7. **Copy and paste** the entire ARM template from the previous artifact
8. **Click** "Save"

### Method 2: Using Deploy to Azure Button (Alternative)

You can also save the template as a file and use the "Deploy to Azure" functionality, but Method 1 is easier for beginners.

## Step 4: Configure Template Parameters

After saving the template, you'll see a parameters form:

### Required Parameters:
- **Subscription**: Your Azure subscription (pre-selected)
- **Resource group**: Select `csv-validation-rg` (created in Step 2)
- **Region**: Should auto-populate from resource group
- **Project Name**: Enter `csvvalidation` (or your preferred name)
- **Administrator Login**: Enter a username for SQL Server (e.g., `sqladmin`)
- **Administrator Login Password**: Create a strong password
  - Must be 8-128 characters
  - Must contain characters from 3 of these categories: uppercase, lowercase, numbers, symbols
  - Example: `MySecurePass123!`

### Optional Parameters (can use defaults):
- **Data Factory Name**: Will auto-generate
- **Storage Account Name**: Will auto-generate
- **SQL Server Name**: Will auto-generate
- **Database Name**: Will auto-generate

## Step 5: Deploy the Template

1. **Review** all parameters
2. **Check** "I agree to the terms and conditions stated above"
3. **Click** "Review + create"
4. **Review** the summary page
5. **Click** "Create"

**⏰ Deployment Time**: 10-15 minutes

## Step 6: Monitor Deployment

1. You'll see a deployment progress page
2. **Wait** for "Your deployment is complete" message
3. **Click** "Go to resource group" to see all created resources

## Step 7: Verify Resources Created

You should see these resources in your resource group:
- ✅ Data Factory (ends with `-adf-`)
- ✅ SQL Server (ends with `-sqlserver-`)
- ✅ SQL Database (ends with `-db`)
- ✅ Storage Account (ends with `storage`)
- ✅ Key Vault (ends with `-kv-`)
- ✅ Log Analytics Workspace (ends with `-law-`)
- ✅ Application Insights (ends with `-ai-`)

## Step 8: Create Database Tables

The ARM template creates the infrastructure, but you need to create the database tables manually.

### 8.1 Connect to SQL Database

1. **Click** on your SQL Database resource
2. **Click** "Query editor (preview)" in the left menu
3. **Enter** your SQL credentials:
   - **Login**: The administrator login you created
   - **Password**: The password you created
4. **Click** "OK"

### 8.2 Create Tables

Copy and paste these SQL scripts one by one:

```sql
-- Create staging table
CREATE TABLE staging_table (
    id INT IDENTITY(1,1) PRIMARY KEY,
    column1 NVARCHAR(255),
    column2 NVARCHAR(255),
    column3 NVARCHAR(255),
    -- Add more columns as needed for your CSV structure
    created_date DATETIME2 DEFAULT GETDATE()
);

-- Create target table
CREATE TABLE target_table (
    id INT IDENTITY(1,1) PRIMARY KEY,
    column1 NVARCHAR(255),
    column2 NVARCHAR(255),
    column3 NVARCHAR(255),
    -- Add more columns as needed for your CSV structure
    created_date DATETIME2 DEFAULT GETDATE(),
    last_modified DATETIME2 DEFAULT GETDATE()
);

-- Create processing log table
CREATE TABLE processing_log (
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    file_name NVARCHAR(255),
    processing_status NVARCHAR(50),
    processing_date DATETIME2 DEFAULT GETDATE(),
    error_message NVARCHAR(MAX)
);
```

### 8.3 Create Stored Procedure

```sql
CREATE PROCEDURE sp_MergeToTargetTable
    @sourceTable NVARCHAR(255),
    @targetTable NVARCHAR(255)
AS
BEGIN
    BEGIN TRY
        -- Simple insert from staging to target
        INSERT INTO target_table (column1, column2, column3)
        SELECT column1, column2, column3
        FROM staging_table;
        
        -- Clear staging table
        TRUNCATE TABLE staging_table;
        
        -- Log success
        INSERT INTO processing_log (file_name, processing_status)
        VALUES ('Merge Process', 'SUCCESS');
        
    END TRY
    BEGIN CATCH
        -- Log error
        INSERT INTO processing_log (file_name, processing_status, error_message)
        VALUES ('Merge Process', 'ERROR', ERROR_MESSAGE());
        
        -- Re-throw error
        THROW;
    END CATCH
END;
```

## Step 9: Configure Storage Account

### 9.1 Get Storage Account Details

1. **Click** on your Storage Account resource
2. **Click** "Access keys" in the left menu
3. **Copy** the "Connection string" for key1 (you'll need this later)

### 9.2 Verify Containers

1. **Click** "Containers" in the left menu
2. **Verify** these containers exist:
   - `source` - for incoming CSV files
   - `staging` - for intermediate processing
   - `processed` - for successfully processed files
   - `logs` - for validation logs

## Step 10: Configure Data Factory Permissions

### 10.1 Give Data Factory Access to Storage

1. **Go** to your Storage Account
2. **Click** "Access control (IAM)" in the left menu
3. **Click** "+ Add" → "Add role assignment"
4. **Select** "Storage Blob Data Contributor" role
5. **Select** "Managed identity" for "Assign access to"
6. **Click** "+ Select members"
7. **Search** for your Data Factory name
8. **Select** your Data Factory
9. **Click** "Review + assign"
10. **Click** "Review + assign" again

### 10.2 Give Data Factory Access to Key Vault

1. **Go** to your Key Vault
2. **Click** "Access control (IAM)" in the left menu
3. **Click** "+ Add" → "Add role assignment"
4. **Select** "Key Vault Secrets User" role
5. **Follow** the same process as above to add your Data Factory

## Step 11: Test the Pipeline

### 11.1 Create Test CSV File

Create a simple CSV file on your computer:

```csv
column1,column2,column3
value1,value2,value3
test1,test2,test3
data1,data2,data3
```

Save this as `test.csv`

### 11.2 Upload Test File

1. **Go** to your Storage Account
2. **Click** "Containers"
3. **Click** on the `source` container
4. **Click** "Upload"
5. **Select** your `test.csv` file
6. **Click** "Upload"

### 11.3 Monitor Pipeline Execution

1. **Go** to your Data Factory resource
2. **Click** "Author & Monitor" (this opens Data Factory Studio)
3. **Click** "Monitor" in the left menu
4. **Click** "Pipeline runs"
5. **Look** for your pipeline execution (it should start automatically)

## Step 12: Verify Results

### 12.1 Check Database Tables

1. **Go** back to your SQL Database
2. **Open** Query editor
3. **Run** these queries:

```sql
-- Check staging table (should be empty after successful processing)
SELECT * FROM staging_table;

-- Check target table (should contain your CSV data)
SELECT * FROM target_table;

-- Check processing log
SELECT * FROM processing_log;
```

### 12.2 Check Storage Containers

1. **Go** to your Storage Account containers
2. **Check** the `logs` container for validation logs
3. **Check** the `processed` container (files may be moved here depending on your configuration)

## Troubleshooting Common Issues

### Issue 1: Pipeline Not Triggering

**Problem**: Files uploaded but pipeline doesn't start

**Solution**:
1. Go to Data Factory Studio
2. Click "Manage" → "Triggers"
3. Find "FileUploadTrigger"
4. Click "Start" if it's not running

### Issue 2: Database Connection Failed

**Problem**: Pipeline fails with database connection error

**Solution**:
1. Go to SQL Server resource
2. Click "Firewalls and virtual networks"
3. Ensure "Allow Azure services and resources to access this server" is ON
4. Add your IP address if accessing from outside Azure

### Issue 3: Permission Denied on Storage

**Problem**: Pipeline fails with storage access error

**Solution**:
1. Repeat Step 10.1 to ensure Data Factory has proper storage permissions
2. Wait 5-10 minutes for permissions to propagate

### Issue 4: Template Deployment Failed

**Problem**: ARM template deployment fails

**Solution**:
1. Check error details in the deployment history
2. Common issues:
   - SQL password doesn't meet complexity requirements
   - Resource names already exist (use different project name)
   - Insufficient permissions

## Cost Management

### Expected Monthly Costs (approximate):
- **SQL Database S0**: ~$15/month
- **Storage Account**: ~$2-5/month (depends on usage)
- **Data Factory**: ~$5-10/month (depends on pipeline runs)
- **Key Vault**: ~$1/month
- **Log Analytics**: ~$2-5/month
- **Total**: ~$25-35/month

### Cost Optimization Tips:
1. **Scale down** SQL Database to Basic tier for development
2. **Use** lifecycle management policies for storage
3. **Monitor** Data Factory pipeline runs
4. **Delete** resources when not needed

## Next Steps

After successful deployment:

1. **Customize** the database schema to match your CSV structure
2. **Modify** the stored procedure for your business logic
3. **Add** data validation rules
4. **Set up** monitoring and alerting
5. **Create** additional pipelines for different file types

## Getting Help

If you encounter issues:
1. **Check** Azure portal notifications
2. **Review** Activity Log in your resource group
3. **Use** Azure support documentation
4. **Consider** Azure support plans for production workloads

## Security Best Practices

1. **Use** Key Vault for all secrets
2. **Enable** Azure AD authentication where possible
3. **Restrict** network access using firewalls
4. **Monitor** access logs regularly
5. **Use** managed identities instead of service principals

---

**Congratulations!** You've successfully deployed a production-ready CSV validation pipeline on Azure. The system will now automatically process any CSV files uploaded to the `source` container.