# Weekend Grocery Specials

Search current flyer offers for up to eight foods, filter the results to the
stores you want, sort prices within each food, and select one offer per item to
see an estimated total. The lowest advertised price is selected by default.

## Run locally

Install Python, then run these commands in the project folder:

```powershell
python -m pip install -r requirements.txt
python .\grocery_web.py
```

The app opens at `http://127.0.0.1:5000`. Keep the terminal open while using it.
Alternatively, double-click **Run Grocery Specials.bat** after installing the
requirements. The original terminal-only checker is still available with
`python .\grocery_tracker.py`.

## Publish the page on GitHub Pages and the API on Render

GitHub Pages hosts the public HTML/CSS/JavaScript page, but it cannot run the
Python code that searches Flipp. The API therefore needs a separate web host.
This project includes a Render Blueprint configured for its free web-service
plan. Render's free service sleeps after 15 minutes without traffic and can
take about a minute to wake; free-tier limits can change. See
[Render's free-instance details](https://render.com/docs/free).

1. Create the public GitHub repository `grocery-specials` and upload this
   project to its root. The `CNAME` file in this project configures the site
   address `groceriesdeals.jopism.com`.
2. In Render, create a **Blueprint** from that repository and deploy the
   `grocery-specials-api` web service defined in `render.yaml`. The free plan
   is selected in the Blueprint. Wait until Render reports the service as live.
3. Copy the service's `onrender.com` address (for example,
   `https://grocery-specials-api.onrender.com`) and set it in `api-config.js`:

   ```javascript
   window.GROCERY_API_URL = "https://YOUR-SERVICE.onrender.com";
   ```

   Do not add a trailing slash. Commit and push that edit.
4. In the repository's **Settings → Pages**, publish from the `main` branch
   and root folder. GitHub reads the custom domain from `CNAME`. For security,
   verify `jopism.com` in your GitHub account's Pages settings before enabling
   the domain if possible.
5. At the DNS provider for `jopism.com`, add a CNAME record with host/name
   `groceriesdeals` and target `<YOUR-GITHUB-USERNAME>.github.io`. Do not
   replace or change the existing records for `jopism.com` itself. DNS changes
   can take up to 24 hours. Once GitHub reports the domain is configured,
   enable **Enforce HTTPS** in Pages settings.
6. Open `https://groceriesdeals.jopism.com`. If the first API request is slow,
   the free service may be waking; retry after it finishes starting.

The `ALLOWED_ORIGINS` setting in `render.yaml` is `*` so a Pages site can call
the API without knowing its final URL in advance. The API is public and is not
password-protected. If you later want to restrict browser origins, set
`ALLOWED_ORIGINS` in Render to your exact Pages origin (for example,
`https://YOUR-NAME.github.io`); do not include the project path.

## Using the app and limitations

- Store checkboxes include the chains configured in `ALLOWED_STORES` in
  `grocery_tracker.py`. Matching is by merchant name, not branch.
- Results are grouped by food and can be sorted by advertised price, store, or
  search match. One offer per food is selected by default; choose a different
  radio option to update the total.
- The total adds the displayed numeric price once per food. It does **not**
  normalize package sizes or units, account for quantities, tax, multi-buy
  conditions, or guarantee that different offers are comparable.
- Results come from Flipp's item-search endpoint, which is not a guaranteed
  public API and may change. Prices and availability can differ at the store.
  Check the original flyer and participating location before travelling.
- Foods and postal codes are sent to Flipp to retrieve offers. When using the
  hosted version, the search also passes through the public API service.

Run the automated tests with:

```powershell
python -m unittest -v test_grocery
```
