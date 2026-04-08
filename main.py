import math

import streamlit as st
from mail_client import MailAnalyzer, SCAN_FOLDERS, DEFAULT_FOLDERS


def get_folder_options() -> dict:
    """Return the folder options dict for the current user's email provider."""
    domain = st.session_state.get("domain")
    return SCAN_FOLDERS.get(domain, DEFAULT_FOLDERS)


def get_selected_imap_folder() -> str:
    """Resolve the selected display label to its IMAP folder name."""
    folder_options = get_folder_options()
    return folder_options.get(st.session_state.scan_folder, "INBOX")


def analyze_emails_component(analyzer):
    if st.button("Analyze Emails"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(current, total):
            progress = current / total
            progress_bar.progress(progress)
            warn_for_large_inboxes = f"""
                    
            Whoa, that's a pretty large inbox! This may take a while...
            We are estimating the analysis to take about {math.floor((total/50)/60)} minutes
            
            _Usually we have seen that more than 40% of the emails are usually from the top five senders_
            So after one cleanup, the next time will be blazing fast!
            """
            status_text.markdown(
                f"""
                Processing email {current}/{total}
                {warn_for_large_inboxes if total > 3000 else ""}
                """
            )

        st.session_state.email_data = analyzer.get_sender_statistics(
            progress_callback=update_progress,
            folder=get_selected_imap_folder(),
        )

        progress_bar.empty()
        status_text.empty()
        st.rerun()


@st.fragment
def sender_list_for_cleanup_component():
    df = st.session_state.email_data

    with st.form("cleanup_form", border=False):
        # Create display columns with cleanup checkbox as first column
        display_df = df[["Sender Name", "Email", "Count", "Unsubscribe Link"]].copy()
        display_df["should_clean_up"] = False
        # Reorder columns to put checkbox first
        display_df = display_df[
            ["should_clean_up", "Sender Name", "Email", "Count", "Unsubscribe Link"]
        ]

        # Create the interactive dataframe
        edited_df = st.data_editor(
            display_df,
            column_config={
                "should_clean_up": st.column_config.CheckboxColumn(
                    "Clean up?",
                    help="Select to clean up emails from this sender",
                    default=False,
                ),
                "Unsubscribe Link": st.column_config.LinkColumn(
                    "Unsubscribe link",
                    help="Click to unsubscribe",
                    display_text="🔗 Unsubscribe",
                    validate="https?://.*",
                ),
                "Count": st.column_config.NumberColumn(
                    "Mail count", help="Number of emails from this sender"
                ),
            },
            hide_index=True,
            use_container_width=True,
            height=500,
        )

        if st.form_submit_button("🧹 Clean Selected Emails", use_container_width=True):
            sender_ids_to_be_cleaned = {
                row["Email"]
                for _, row in edited_df.iterrows()
                if row["should_clean_up"]
            }
            if not sender_ids_to_be_cleaned:
                st.toast("No senders selected for cleanup!")
            else:
                st.write(
                    f"Cleaning up emails from: {', '.join(sender_ids_to_be_cleaned)}"
                )
                st.toast(
                    "This may take a while depending on the number of emails. Please be patient!"
                )
                analyzer = MailAnalyzer(
                    st.session_state.email_address, st.session_state.app_password
                )
                # TODO: move to bulk delete
                for sender in sender_ids_to_be_cleaned:
                    deleted_count = analyzer.delete_emails_from_sender(
                        sender, folder=get_selected_imap_folder()
                    )
                    st.toast(f"Moved {deleted_count} emails from {sender} to the bin!")

                # Remove deleted senders from the dataframe instead of clearing.
                # Avoids forcing a full re-scan after every delete.
                st.session_state.email_data = st.session_state.email_data[
                    ~st.session_state.email_data["Email"].isin(sender_ids_to_be_cleaned)
                ].reset_index(drop=True)
                st.rerun()


def email_cleanup_component():
    analyzer = MailAnalyzer(
        st.session_state.email_address, st.session_state.app_password
    )
    # Show "Analyze Emails" button only if sender_stats is not populated
    if st.session_state.email_data is None:
        analyze_emails_component(analyzer)
        return

    sender_list_for_cleanup_component()


def sidebar_component():
    st.sidebar.header("Authentication")

    with st.sidebar:
        with st.form("authentication_form"):
            st.session_state.email_address = st.text_input(
                "Gmail/Yahoo Address",
                value=st.session_state.email_address,
                type="default",
            )
            st.session_state.app_password = st.text_input(
                "Gmail/Yahoo App Password",
                value=st.session_state.app_password,
                type="password",
            )

            if st.form_submit_button("Connect"):
                if st.session_state.email_address and st.session_state.app_password:
                    analyzer = MailAnalyzer(
                        st.session_state.email_address, st.session_state.app_password
                    )
                    test_conn = analyzer.connect()
                    if test_conn:
                        test_conn.logout()
                        # Store domain so folder options can be scoped per provider
                        st.session_state.domain = (
                            st.session_state.email_address.lower().split("@")[-1]
                        )
                        st.session_state.scan_folder = "Inbox"
                        st.session_state.email_data = None
                        st.success("Successfully connected!")
                        st.rerun()

        st.sidebar.header("Scan Options")
        folder_options = list(get_folder_options().keys())
        st.session_state.scan_folder = st.sidebar.selectbox(
            "Folder to scan",
            options=folder_options,
            index=folder_options.index(st.session_state.scan_folder)
            if st.session_state.scan_folder in folder_options
            else 0,
        )

        # Add a button to star the repository
        st.sidebar.markdown(
            """
            ---
            ⭐️ [Star this project on GitHub](https://github.com/BharatKalluri/cleanmail)
            
            🔗 [bharatkalluri.com](https://bharatkalluri.com)
            """
        )


def main():
    st.set_page_config(page_title="CleanMail", layout="wide")

    # Use session state to store email credentials and sender stats
    if "email_address" not in st.session_state:
        st.session_state.email_address = None
    if "app_password" not in st.session_state:
        st.session_state.app_password = None
    if "email_data" not in st.session_state:
        st.session_state.email_data = None
    if "domain" not in st.session_state:
        st.session_state.domain = None
    if "scan_folder" not in st.session_state:
        st.session_state.scan_folder = "Inbox"

    # Sidebar for authentication
    sidebar_component()

    # Title row with refresh button
    title_col, reset_col = st.columns([7, 1])
    with title_col:
        st.title("CleanMail")
    with reset_col:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.email_data = None
            st.rerun()

    if st.session_state.email_address and st.session_state.app_password:
        email_cleanup_component()
    else:
        st.info("Please authenticate using your credentials in the sidebar.")
        st.markdown(
            """
        ### Instructions:
        1. Enter your Gmail or Yahoo address
        2. Enter your [Gmail App Password](https://myaccount.google.com/apppasswords) or [Yahoo App Password](https://help.yahoo.com/kb/SLN15241.html)
        3. Select the folder to scan from the sidebar
        4. Click Connect to start analyzing your inbox
        
        **Note:** _This app requires a App Password, not your regular password_!
        """
        )


if __name__ == "__main__":
    main()
