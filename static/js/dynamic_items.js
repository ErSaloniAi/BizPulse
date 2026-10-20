/**
 * Dynamic line-item manager for Sales Bill Book and Purchase Invoices
 */
function initDynamicItems(options) {
    const tableBody = document.getElementById(options.tableBodyId);
    const addRowBtn = document.getElementById(options.addRowBtnId);
    const grandTotalEl = document.getElementById(options.grandTotalId);
    const amountPaidInput = document.getElementById(options.amountPaidId);
    const outstandingEl = document.getElementById(options.outstandingId);
    const paymentStatusSelect = document.getElementById(options.paymentStatusId);
    const productsData = options.products || [];
    const isSale = options.isSale || false;

    // Helper to format currency
    function fmt(val) {
        return parseFloat(val || 0).toFixed(2);
    }

    // Function to calculate a single row total
    function updateRowTotal(row) {
        const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
        const rate = parseFloat(row.querySelector('.item-rate').value) || 0;
        let lineTotal = qty * rate;

        if (isSale) {
            const discountInput = row.querySelector('.item-discount');
            const discount = parseFloat(discountInput ? discountInput.value : 0) || 0;
            lineTotal = Math.max(0, lineTotal - discount);
        }

        row.querySelector('.item-total').innerText = fmt(lineTotal);
        updateGrandTotal();
    }

    // Recalculate bill/invoice grand total and outstanding
    function updateGrandTotal() {
        let total = 0;
        tableBody.querySelectorAll('tr').forEach(row => {
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const rate = parseFloat(row.querySelector('.item-rate').value) || 0;
            let rowTotal = qty * rate;
            if (isSale) {
                const discount = parseFloat(row.querySelector('.item-discount').value) || 0;
                rowTotal = Math.max(0, rowTotal - discount);
            }
            total += rowTotal;
        });

        if (grandTotalEl) {
            grandTotalEl.innerText = fmt(total);
        }

        const paid = parseFloat(amountPaidInput ? amountPaidInput.value : 0) || 0;
        const outstanding = Math.max(0, total - paid);

        if (outstandingEl) {
            outstandingEl.innerText = fmt(outstanding);
        }

        // Auto update payment status dropdown if user hasn't explicitly locked it
        if (paymentStatusSelect && document.activeElement === amountPaidInput) {
            if (paid >= total && total > 0) {
                paymentStatusSelect.value = 'paid';
            } else if (paid > 0) {
                paymentStatusSelect.value = 'partial';
            } else {
                paymentStatusSelect.value = 'unpaid';
            }
        }
    }

    // Add a new row to table
    function addNewRow(selectedProduct = null) {
        const row = document.createElement('tr');
        row.className = 'item-row align-middle';

        let productOptions = '<option value="">-- Select Product --</option>';
        productsData.forEach(p => {
            const isSelected = selectedProduct && selectedProduct.id === p.id ? 'selected' : '';
            const brandStr = p.brand ? ` (${p.brand})` : '';
            productOptions += `<option value="${p.id}" data-price="${p.price || ''}" data-cost="${p.purchase_cost || ''}" data-unit="${p.unit || ''}" data-stock="${p.stock || '0'}" ${isSelected}>${p.name}${brandStr} [${p.unit}]</option>`;
        });

        if (isSale) {
            row.innerHTML = `
                <td>
                    <select name="product_id[]" class="form-select form-select-sm item-product" required>
                        ${productOptions}
                    </select>
                    <small class="text-muted d-block mt-1 available-stock-text"></small>
                </td>
                <td style="width: 120px;">
                    <input type="number" name="quantity[]" class="form-control form-control-sm item-qty text-end" min="0.01" step="0.01" value="1" required>
                </td>
                <td style="width: 130px;">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">₹</span>
                        <input type="number" name="price[]" class="form-control item-rate text-end" min="0" step="0.01" value="0.00" required>
                    </div>
                </td>
                <td style="width: 110px;">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">₹</span>
                        <input type="number" name="discount[]" class="form-control item-discount text-end" min="0" step="0.01" value="0.00">
                    </div>
                </td>
                <td style="width: 120px;" class="text-end fw-semibold">
                    ₹<span class="item-total">0.00</span>
                </td>
                <td style="width: 50px;" class="text-center">
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-1 remove-row-btn" title="Remove row">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
        } else {
            // Purchase row
            row.innerHTML = `
                <td>
                    <select name="product_id[]" class="form-select form-select-sm item-product" required>
                        ${productOptions}
                    </select>
                    <small class="text-muted d-block mt-1 available-stock-text"></small>
                </td>
                <td style="width: 130px;">
                    <input type="number" name="quantity[]" class="form-control form-control-sm item-qty text-end" min="0.01" step="0.01" value="1" required>
                </td>
                <td style="width: 140px;">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">₹</span>
                        <input type="number" name="cost[]" class="form-control item-rate text-end" min="0" step="0.01" value="0.00" required>
                    </div>
                </td>
                <td style="width: 130px;" class="text-end fw-semibold">
                    ₹<span class="item-total">0.00</span>
                </td>
                <td style="width: 50px;" class="text-center">
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-1 remove-row-btn" title="Remove row">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
        }

        tableBody.appendChild(row);

        // Attach event listeners to row inputs
        const productSelect = row.querySelector('.item-product');
        const qtyInput = row.querySelector('.item-qty');
        const rateInput = row.querySelector('.item-rate');
        const removeBtn = row.querySelector('.remove-row-btn');
        const stockText = row.querySelector('.available-stock-text');

        productSelect.addEventListener('change', function() {
            const selectedOpt = this.options[this.selectedIndex];
            if (selectedOpt && selectedOpt.value) {
                if (isSale) {
                    rateInput.value = selectedOpt.getAttribute('data-price') || '0.00';
                    const stock = selectedOpt.getAttribute('data-stock') || '0';
                    const unit = selectedOpt.getAttribute('data-unit') || '';
                    stockText.innerText = `In Stock: ${stock} ${unit}`;
                    if (parseFloat(stock) <= 0) {
                        stockText.className = 'text-danger fw-bold d-block mt-1 available-stock-text';
                    } else {
                        stockText.className = 'text-success d-block mt-1 available-stock-text';
                    }
                } else {
                    rateInput.value = selectedOpt.getAttribute('data-cost') || '0.00';
                    const stock = selectedOpt.getAttribute('data-stock') || '0';
                    stockText.innerText = `Current Stock: ${stock}`;
                }
            } else {
                rateInput.value = '0.00';
                stockText.innerText = '';
            }
            updateRowTotal(row);
        });

        qtyInput.addEventListener('input', () => updateRowTotal(row));
        rateInput.addEventListener('input', () => updateRowTotal(row));

        if (isSale) {
            const discountInput = row.querySelector('.item-discount');
            if (discountInput) {
                discountInput.addEventListener('input', () => updateRowTotal(row));
            }
        }

        removeBtn.addEventListener('click', function() {
            if (tableBody.querySelectorAll('tr').length > 1) {
                row.remove();
                updateGrandTotal();
            } else {
                alert("A bill/invoice must have at least one product row.");
            }
        });

        updateRowTotal(row);
    }

    if (addRowBtn) {
        addRowBtn.addEventListener('click', () => addNewRow());
    }

    if (amountPaidInput) {
        amountPaidInput.addEventListener('input', updateGrandTotal);
    }

    if (paymentStatusSelect) {
        paymentStatusSelect.addEventListener('change', function() {
            const total = parseFloat(grandTotalEl ? grandTotalEl.innerText : 0) || 0;
            if (this.value === 'paid') {
                if (amountPaidInput) amountPaidInput.value = fmt(total);
            } else if (this.value === 'unpaid') {
                if (amountPaidInput) amountPaidInput.value = '0.00';
            }
            updateGrandTotal();
        });
    }

    // Add initial row if table empty
    if (tableBody && tableBody.querySelectorAll('tr').length === 0) {
        addNewRow();
    }
}
