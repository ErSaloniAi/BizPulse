# BizPulse — Business Analysis Website for Retail Stationery Shops

**BizPulse** is a practical, data-driven business analysis and inventory management web application tailored specifically for small retail stationery shops. It digitizes traditional handwritten bill books, opening stock registers, distributor purchases, and operating expenses into real-time business intelligence and financial insights.

Built with **Python**, **Django**, **PostgreSQL**, **Bootstrap 5**, and **Chart.js**.

---

## Key Features

1. **Physical Bill-Book Digitization (Sales Module)**:
   - Matches the shopkeeper's physical bill book format: Bill No, Date, M/s (Customer/School/Business name), Product items, Quantities, Rates, Discounts, and Bill Total.
   - Dynamic line-item entry with live rate autofill, line total calculation, and stock validation.
   - Prevents sales if stock would fall negative.
   - Captures moving weighted-average unit cost as `historical_cost_per_unit` at the moment of sale, guaranteeing that past profit reports remain immutable even when future costs change.
   - Tracks payment status: Paid, Partially Paid, and Unpaid with outstanding balances.
   - Safe financial voiding workflow that automatically restores inventory back to stock.

2. **Stock Record & Inventory Valuation (Inventory Module)**:
   - Records initial opening stock baselines upon onboarding.
   - Moving Weighted-Average Costing (Perpetual Inventory System).
   - Supports retail stationery units: *Piece*, *Packet*, *Box*, *Dozen*, *Bundle*, *Ream*, *Other*.
   - Intelligent duplicate detection (by Name + Brand + Unit) to prevent accidental double-entry while allowing intentional variants.
   - Automatic low-stock alert warnings when current stock falls to or below minimum stock level.
   - Manual stock adjustment and damage/write-off logging with complete audit trails.

3. **Distributor Purchases (Purchases Module)**:
   - Records supplier invoices and wholesale purchases.
   - Atomically increments stock balances and updates weighted-average inventory costs.
   - **Accounting Integrity**: Purchases are correctly capitalized into inventory assets and are **never** mixed with operating expenses on profit reports.
   - Tracks supplier payables and credit balances.

4. **Operating Expenses (Single-Table Architecture)**:
   - Single expenses table with categorized tracking across 14 standard categories: *Rent, Electricity, Water, Internet & Telephone, Transportation & Delivery, Marketing, Repairs & Maintenance, Packaging, Employee Salaries, Bank Charges, Cleaning, Software & Subscriptions, Licences & Fees, Other Business Expenses*.
   - Allows creating custom shop-specific expense categories.
   - Distinguishes expenses incurred (for P&L) from actual payments made (for Cash Flow).

5. **Financial Analysis & Business Intelligence Dashboard**:
   - **Total Sales Revenue**: \(\sum \text{Sale line totals}\) for confirmed bills.
   - **Cost of Goods Sold (COGS)**: \(\sum (\text{Qty Sold} \times \text{Historical Cost Per Unit})\).
   - **Gross Profit & Gross Profit Margin %**: Net Sales Revenue minus COGS.
   - **Operating Expenses**: Total overhead costs incurred in the period.
   - **Net Operating Profit Estimate & Net Margin %**: Gross Profit minus Operating Expenses.
   - **Distinction between Cash Flow and Profit**:
     - *Net Operating Profit* = Incurred revenue minus inventory sold minus incurred expenses.
     - *Net Cash Flow* = Actual cash collected minus actual payments made.
   - **Period Comparisons**: Growth percentage vs prior period for sales and profit.
   - **Interactive Date Filters**: *Today*, *Last 7 Days*, *This Month*, *Previous Month*, and *Custom Range*.
   - **Chart.js Visualizations**: Daily sales trend line, Monthly revenue vs profit combo chart, Expense doughnut breakdown, and Top-selling products bar chart.
   - **Empty State Guide**: Step-by-step onboarding for newly initialized databases.

6. **Comprehensive Reports & Export Hub**:
   - 8 Database-driven reports:
     1. Daily Sales Report
     2. Monthly Sales Report
     3. Profit & Loss Summary Statement
     4. Product-wise Sales & Profitability Report
     5. Expense Category Breakdown Report
     6. Purchases Register Report
     7. Current Stock Valuation Report
     8. Low-Stock Restocking Report
   - **CSV Export**: Clean spreadsheet download for every report.
   - **Professional PDF Generation**: Built with **ReportLab** featuring shop branding, GSTIN, tabular grids, alternating row colors, right-aligned monetary values, and bold summary rows.

7. **Business Settings & Shop Profile**:
   - Customizable Shop Name, Owner Name, Contact Phone, Address, GSTIN, Currency Symbol (`₹`), and Default Low-Stock Threshold.

---

## Technology Stack

- **Backend**: Python 3.10+, Django 5/6, Django ORM, Django Forms, Django Authentication
- **Database**: PostgreSQL (psycopg2-binary)
- **Database Management Tool**: pgAdmin 4
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla ES6), Bootstrap 5.3, Bootstrap Icons 1.11, Chart.js 4.4
- **Document Generation**: ReportLab 4+ (PDF Export), Python csv module (CSV Export)
- **Configuration**: python-dotenv

---

## Installation & Setup Instructions

### Prerequisites
1. Python 3.10 or higher.
2. PostgreSQL 14+ installed and running.
3. pgAdmin 4 (optional, for visual database administration).

---

### Step 1: PostgreSQL Setup & pgAdmin 4 Configuration

#### Option A: Using pgAdmin 4
1. Open **pgAdmin 4** on your computer.
2. In the left navigation tree, expand **Servers** and enter your master password to connect to the PostgreSQL server.
3. Right-click on **Databases** &rarr; select **Create** &rarr; **Database...**.
4. In the dialog:
   - **Database**: `bizpulse`
   - **Owner**: `postgres` (or your preferred user)
5. Click **Save**.

#### Option B: Using SQL Shell (psql) or Command Line
```sql
CREATE DATABASE bizpulse;
```

---

### Step 2: Clone or Navigate to Project Directory
```bash
cd c:\Users\Lenovo\OneDrive\BizPulse
```

---

### Step 3: Install Python Dependencies
```bash
pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables (.env)
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Open `.env` and verify your PostgreSQL credentials:
```ini
SECRET_KEY=your-secure-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL Settings
DB_NAME=bizpulse
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

---

### Step 5: Run Database Migrations
Apply all schema tables and default seed data (14 expense categories & default business setting):
```bash
python manage.py migrate
```

---

### Step 6: Create or Verify Superuser
A default administrative account has been pre-configured:
- **Username**: `admin`
- **Password**: `admin123`

To create an additional administrator:
```bash
python manage.py createsuperuser
```

---

### Step 7: Run Automated Test Suite
Verify that all 19 automated test cases pass against PostgreSQL:
```bash
python manage.py test tests --verbosity=2
```

---

### Step 8: Start the Development Server
```bash
python manage.py runserver
```
Open your web browser and visit:
```
http://127.0.0.1:8000/
```
Log in using your administrator credentials.

---

## Daily Shopkeeper Workflow Guide

```
+-------------------------------------------------------------+
|                     DAILY BIZPULSE FLOW                     |
+-------------------------------------------------------------+
| 1. Morning Setup / Onboarding                               |
|    Stock Record -> Add Opening Stock / New Product          |
|    (Sets up products, baseline quantities, and units)       |
+-------------------------------------------------------------+
| 2. Customer Visits & Sales                                  |
|    Sold Products -> New Bill                                |
|    (Select product, enter quantity, rate, discount,         |
|     record payment, save bill & auto-deduct stock)          |
+-------------------------------------------------------------+
| 3. Receiving Supplier Deliveries                            |
|    Purchases -> Record New Purchase                         |
|    (Select supplier, enter items, costs, auto-increment     |
|     stock, and update moving weighted average cost)         |
+-------------------------------------------------------------+
| 4. Paying Shop Expenses                                     |
|    Expenses -> Record Expense                               |
|    (Log rent, electricity, tea, packaging, or wages)        |
+-------------------------------------------------------------+
| 5. Evening Business Review                                  |
|    Dashboard -> Review Today's Sales, Gross Profit,         |
|    Net Profit Estimate, Cash Received, and Low-Stock items  |
|    Reports -> Download daily PDF statement or export CSV    |
+-------------------------------------------------------------+
```

---

## Inventory Costing Methodology

BizPulse uses **Perpetual Moving Weighted-Average Costing**:
$$\text{New Average Cost} = \frac{(\text{Current Qty} \times \text{Current Avg Cost}) + (\text{Purchased Qty} \times \text{Purchase Cost})}{\text{Current Qty} + \text{Purchased Qty}}$$

When a sales bill is saved:
- Every `SaleItem` stores a snapshot of the product's moving weighted-average cost in `historical_cost_per_unit`.
- Future purchase cost fluctuations or product price changes **never** alter previous sales COGS or historical profit reports.
- Voiding a bill restores stock atomically.
- Voiding a purchase reverses the stock addition atomically.

---

## License & Credits

Developed for small retail stationery shops to replace paper bill books and handwritten registers with automated business intelligence.
