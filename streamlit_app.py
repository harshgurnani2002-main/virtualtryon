import streamlit as st
import requests

# Configure Streamlit page
st.set_page_config(page_title="Virtual Try-On Studio", page_icon="👕", layout="centered")

st.title("👕 AI Virtual Try-On Studio")
st.markdown("Upload a picture of a garment and a picture of yourself to see how it looks on you!")

API_BASE_URL = "http://127.0.0.1:8000/api"

with st.container():
    st.header("1. Upload Product Garment")
    product_file = st.file_uploader("Select the garment image (e.g., shirt, dress)", type=['png', 'jpg', 'jpeg'])

with st.container():
    st.header("2. Provide Person Image")
    input_method = st.radio("How would you like to provide your image?", ["Upload File", "Take a Picture"])
    
    person_file = None
    if input_method == "Upload File":
        person_file = st.file_uploader("Upload a photo of yourself", type=['png', 'jpg', 'jpeg'])
    else:
        person_file = st.camera_input("Take a picture")

# Show previews
if product_file and person_file:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Garment")
        st.image(product_file, use_container_width=True)
    with col2:
        st.subheader("Person Model")
        st.image(person_file, use_container_width=True)

st.divider()

if st.button("✨ Generate Virtual Try-On ✨", use_container_width=True):
    if not product_file:
        st.error("Please provide a product (garment) image.")
    elif not person_file:
        st.error("Please provide a person image.")
    else:
        with st.spinner("Uploading and generating your Virtual Try-On... This will take a few minutes. Please wait..."):
            try:
                # 1. Create Product
                prod_data = {"name": getattr(product_file, "name", "Garment")}
                prod_files = {
                    "image": (getattr(product_file, "name", "garment.jpg"), 
                              product_file.getvalue(), 
                              getattr(product_file, "type", "image/jpeg"))
                }
                
                prod_resp = requests.post(f"{API_BASE_URL}/products/", data=prod_data, files=prod_files, timeout=60)
                
                if not prod_resp.ok:
                    st.error(f"Failed to upload product: {prod_resp.text}")
                else:
                    product_data = prod_resp.json()
                    product_id = product_data.get("id")
                    
                    st.info(f"Garment uploaded successfully! Initiating generation...")
                    
                    # 2. Call Try-On API
                    tryon_data = {"product": product_id}
                    tryon_files = {
                        "person_image": (getattr(person_file, "name", "person.jpg"), 
                                         person_file.getvalue(), 
                                         getattr(person_file, "type", "image/jpeg"))
                    }
                    
                    # TryOn process is synchronous and can take a while via NanoBanana
                    tryon_resp = requests.post(f"{API_BASE_URL}/tryon/", data=tryon_data, files=tryon_files, timeout=1200) # 20 mins timeout 
                    
                    if tryon_resp.ok:
                        result = tryon_resp.json()
                        output_url = result.get("output_image_url")
                        
                        if output_url:
                            st.success("Generation Complete! 🎉")
                            st.image(output_url, caption="Your Virtual Try-On Result", use_container_width=True)
                        else:
                            st.error("Generation succeeded but no output URL was provided in the response.")
                            st.json(result)
                    else:
                        st.error(f"Try-On Generation Failed! (Status Code: {tryon_resp.status_code})")
                        st.json(tryon_resp.json() if "application/json" in tryon_resp.headers.get("Content-Type", "") else {"text": tryon_resp.text})
            
            except requests.exceptions.Timeout:
                st.error("The request timed out. Virtual try-ons can take a while to process. Please check the backend terminal to see if it's still generating.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
