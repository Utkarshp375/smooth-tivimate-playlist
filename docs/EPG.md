# EPG setup for TiviMate

1. Obtain an XMLTV feed that you are authorized to use.
2. In GitHub, open Settings -> Secrets and variables -> Actions -> Variables.
3. Add a repository variable named EPG_URL containing the HTTPS XMLTV URL.
   Do not commit credentials, cookies, or private tokens into this repository.
4. Run the Update TiviMate playlist workflow manually, or wait for its schedule.
5. After a successful download, use this URL in TiviMate:

   https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml

The feed must contain XMLTV data. This project does not scrape paid services or
bypass DRM, authentication, or geographic restrictions. If EPG_URL is absent,
the workflow skips EPG download.
