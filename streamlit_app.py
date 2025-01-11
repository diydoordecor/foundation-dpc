import streamlit as st
import pandas as pd

def preprocess_product(row, columns, ignore_prefix):
    description = row.get(columns['description'], '')
    if pd.notnull(description) and description.startswith(ignore_prefix):
        description = description[len(ignore_prefix):]
    return f"{row.get(columns['name'], '')} {description} {row.get(columns['package_qty'], '')} ({str(row.get(columns['form'], '')).strip().lower()})"

def calculate_quantity_to_order(row, target_months):
    avg_dispensed = row['total_units_past_6_months'] / (6 / target_months)
    max_dispensed = max(row['total_units_past_2_months'], avg_dispensed)
    target_qty = row['target_qty_on_hand_override'] if pd.notnull(row['target_qty_on_hand_override']) else max_dispensed
    return max(0, target_qty - row['on_hand'])

def standardize_columns(df):
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    return df

def main():
    st.title("Medication Order Calculator")
    st.markdown("This app helps calculate the amount of each medication and product to order based on usage and current inventory.")

    target_months = st.slider("Select Target Months On Hand", 1, 12, 2)

    uploaded_files = {
        'meds_on_hand': st.file_uploader("Upload Meds on Hand CSV", type="csv"),
        'products_on_hand': st.file_uploader("Upload Products on Hand CSV", type="csv"),
        'dispensed_past_2_months': st.file_uploader("Upload Dispensed Past 2 Months CSV", type="csv"),
        'dispensed_past_6_months': st.file_uploader("Upload Dispensed Past 6 Months CSV", type="csv")
    }

    if all(uploaded_files.values()):
        # Read and standardize column names
        meds_on_hand = standardize_columns(pd.read_csv(uploaded_files['meds_on_hand']))
        products_on_hand = standardize_columns(pd.read_csv(uploaded_files['products_on_hand']))
        dispensed_2_months = standardize_columns(pd.read_csv(uploaded_files['dispensed_past_2_months']))
        dispensed_6_months = standardize_columns(pd.read_csv(uploaded_files['dispensed_past_6_months']))

        # Preprocess Products
        meds_on_hand['product'] = meds_on_hand.apply(preprocess_product, axis=1, 
            columns={'name': 'generic_name', 'description': 'description', 'package_qty': 'package_qty', 'form': 'form'}, ignore_prefix='1 x ')

        products_on_hand['product'] = products_on_hand.apply(preprocess_product, axis=1, 
            columns={'name': 'brand', 'description': 'description', 'package_qty': 'package_qty', 'form': 'units'}, ignore_prefix='1 x ')

        dispensed_2_months['product'] = dispensed_2_months.apply(lambda row: preprocess_product(row, 
            {'name': 'generic', 'description': 'qty_x_form', 'package_qty': 'containers', 'form': 'containers'}, ignore_prefix='1 x '), axis=1)

        dispensed_6_months['product'] = dispensed_6_months.apply(lambda row: preprocess_product(row, 
            {'name': 'generic', 'description': 'qty_x_form', 'package_qty': 'containers', 'form': 'containers'}, ignore_prefix='1 x '), axis=1)

        # Rename for consistency
        dispensed_2_months = dispensed_2_months.rename(columns={'containers': 'total_units_past_2_months'})
        dispensed_6_months = dispensed_6_months.rename(columns={'containers': 'total_units_past_6_months'})
        meds_on_hand = meds_on_hand.rename(columns={'containers': 'on_hand'})

        # Merge and calculate quantities
        combined_data = pd.merge(
            dispensed_2_months[['product', 'total_units_past_2_months']], 
            dispensed_6_months[['product', 'total_units_past_6_months']], 
            on='product', 
            how='outer'
        )
        combined_data = pd.merge(combined_data, products_on_hand[['product', 'on_hand']], on='product', how='left')
        combined_data = pd.merge(combined_data, meds_on_hand[['product', 'on_hand']], on='product', how='left', suffixes=('', '_meds'))

        # Resolve potential conflicts in `on_hand`
        combined_data['on_hand'] = combined_data['on_hand'].combine_first(combined_data['on_hand_meds'])
        combined_data.drop(columns=['on_hand_meds'], inplace=True)

        # Debug unmatched products
        unmatched_products = meds_on_hand[~meds_on_hand['product'].isin(combined_data['product'])]
        if not unmatched_products.empty:
            st.write("Unmatched Products in Meds on Hand:", unmatched_products[['product', 'on_hand']])

        # Add editable column for target overrides
        if 'target_qty_on_hand_override' not in combined_data.columns:
            combined_data['target_qty_on_hand_override'] = None

        combined_data['target_qty_on_hand_override'] = st.data_editor(combined_data['target_qty_on_hand_override'])

        # Check for required columns before calculating
        required_columns = ['total_units_past_6_months', 'total_units_past_2_months', 'on_hand']
        missing_columns = [col for col in required_columns if col not in combined_data.columns]
        if missing_columns:
            st.error(f"Missing required columns for calculation: {missing_columns}")
            return

        combined_data['qty_to_order'] = combined_data.apply(calculate_quantity_to_order, axis=1, target_months=target_months)

        # Display results
        st.write("Calculated Quantities to Order:")
        st.dataframe(combined_data[['product', 'qty_to_order', 'total_units_past_2_months', 
                                    'total_units_past_6_months', 'on_hand', 'target_qty_on_hand_override']])

        # Download Option
        csv = combined_data.to_csv(index=False)
        st.download_button("Download Results", csv, "order_quantities.csv", "text/csv")

if __name__ == '__main__':
    main()
