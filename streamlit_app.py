import streamlit as st
import pandas as pd

def preprocess_product(row, columns, ignore_prefix):
    description = row[columns['description']]
    if pd.notnull(description) and description.startswith(ignore_prefix):
        description = description[len(ignore_prefix):]
    return f"{row[columns['name']]} {description} {row[columns['package_qty']]} ({str(row[columns['form']]).strip().lower()})"

def calculate_quantity_to_order(row, target_months):
    avg_dispensed = row['Dispensed Past 6 Months'] / (6 / target_months)
    max_dispensed = max(row['Dispensed Past 2 Months'], avg_dispensed)
    target_qty = row['Target QTY on Hand (Override)'] if pd.notnull(row['Target QTY on Hand (Override)']) else max_dispensed
    return max(0, target_qty - row['On Hand'])

def main():
    st.title("Medication Order Calculator")
    st.markdown("This app helps calculate the amount of each medication and product to order based on usage and current inventory.")

    target_months = st.slider("Select Target Months On Hand", 1, 12, 2)

    uploaded_files = {
        'Meds on Hand': st.file_uploader("Upload Meds on Hand CSV", type="csv"),
        'Products on Hand': st.file_uploader("Upload Products on Hand CSV", type="csv"),
        'Dispensed Past 2 Months': st.file_uploader("Upload Dispensed Past 2 Months CSV", type="csv"),
        'Dispensed Past 6 Months': st.file_uploader("Upload Dispensed Past 6 Months CSV", type="csv")
    }

    if all(uploaded_files.values()):
        # Read CSVs into DataFrames
        meds_on_hand = pd.read_csv(uploaded_files['Meds on Hand'])
        products_on_hand = pd.read_csv(uploaded_files['Products on Hand'])
        dispensed_2_months = pd.read_csv(uploaded_files['Dispensed Past 2 Months'])
        dispensed_6_months = pd.read_csv(uploaded_files['Dispensed Past 6 Months'])

        # Preprocess Products
        meds_on_hand['Product'] = meds_on_hand.apply(preprocess_product, axis=1, 
            columns={'name': 'Generic Name', 'description': 'Description', 'package_qty': 'Package Qty', 'form': 'Form'}, ignore_prefix='1 x ')

        products_on_hand['Product'] = products_on_hand.apply(preprocess_product, axis=1, 
            columns={'name': 'Brand', 'description': 'Description', 'package_qty': 'Package Qty', 'form': 'Units'}, ignore_prefix='1 x ')

        # Handle missing Product columns by creating placeholder values
        if 'Product' not in dispensed_2_months.columns:
            dispensed_2_months['Product'] = dispensed_2_months.apply(lambda row: preprocess_product(row, 
                {'name': 'Generic Name', 'description': 'Description', 'package_qty': 'Package Qty', 'form': 'Form'}, ignore_prefix='1 x '), axis=1)

        if 'Product' not in dispensed_6_months.columns:
            dispensed_6_months['Product'] = dispensed_6_months.apply(lambda row: preprocess_product(row, 
                {'name': 'Generic Name', 'description': 'Description', 'package_qty': 'Package Qty', 'form': 'Form'}, ignore_prefix='1 x '), axis=1)

        # Merge and calculate quantities
        combined_data = pd.merge(dispensed_2_months, dispensed_6_months, on='Product', suffixes=(' Past 2 Months', ' Past 6 Months'), how='outer')
        combined_data = pd.merge(combined_data, products_on_hand[['Product', 'On Hand']], on='Product', how='left')
        combined_data = pd.merge(combined_data, meds_on_hand[['Product', 'Containers']], on='Product', how='left')

        combined_data['Target QTY on Hand (Override)'] = st.experimental_data_editor(
            combined_data.get('Target QTY on Hand (Override)', pd.Series(dtype='float')))

        combined_data['QTY to Order'] = combined_data.apply(calculate_quantity_to_order, axis=1, target_months=target_months)

        # Display results
        st.write("Calculated Quantities to Order:")
        st.dataframe(combined_data[['Product', 'QTY to Order', 'Containers', 'Dispensed Past 2 Months', 
                                    'Dispensed Past 6 Months', 'On Hand', 'Target QTY on Hand (Override)']])

        # Download Option
        csv = combined_data.to_csv(index=False)
        st.download_button("Download Results", csv, "order_quantities.csv", "text/csv")

if __name__ == '__main__':
    main()