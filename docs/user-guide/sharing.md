# Sharing articles

Share interesting articles with other users on your News Dashboard instance
using the built-in **Sharing** feature. This lets you send a link to an
article that, when opened by the recipient, shows the article in their own
interface with their own triage state.

## How sharing works

When you share an article:
1. The system generates a **single-use, time-limited token** for that article
2. It creates a share record linking you (the sender), the recipient, and the
   article
3. You give the recipient a URL like: `https://your-instance.com/article/123?share=abc123`
4. When the recipient opens that link:
   - The app validates the token (ensures it's unused and not expired)
   - The article loads in their interface
   - They can read, triage, star, etc. — just like any other article
   - Their actions are recorded under their own user account
   - The share token is marked as used and cannot be reused

Sharing is **not** forwarding the article text or URL — it's granting access
to the article within the app, respecting permissions and personal state.

## Sharing from the article view

To share an article you're viewing:

1. Open the article (tap/click on it in any feed)
2. In the article header, tap the **Share** icon (usually three dots connected
   by lines, or a paper airplane)
3. In the share dialog:
   - Enter the recipient's username (must exist on your instance)
   - Optionally add a note explaining why you're sharing
   - Tap "Send share"
4. The recipient receives a notification (in-app bell, and optionally email
   or push if configured) with your note and a link to accept the share

## Sharing from feeds

You can also share directly from any article list (Today Feed, Saved, etc.):

1. Hover over or long-press an article card
2. Look for the **Share** action in the article menu
3. Follow the same steps as above

## Receiving shares

When someone shares an article with you:
- You'll see a notification in the app (bell icon in the header)
- Optionally, you may receive an email or push notification (if enabled)
- The notification shows:
  - Who shared it
  - Their note (if any)
  - The article title and source
- Tap the notification to go straight to the article
- Alternatively, visit the **Shares** tab (in your user menu) to see all
  incoming and outgoing shares

## What the recipient sees

When the recipient opens the shared article:
- The article loads normally (title, summary, body, metadata)
- They see any tags you've applied (tags are visible to all users)
- They do **not** see:
  - Your personal triage state (your Done/Skip/Star/etc.)
  - Your personal notes (if notes feature is enabled)
  - Your read/save timestamps
- They interact with the article as if they discovered it themselves:
  - Their triage actions are recorded under their username
  - They can star, save, skip, or mark as done
  - Their own tags can be added (separate from yours)

## Share expiration and limits

Shares are designed to be private and temporary:
- **Single-use**: once the recipient opens the link, it cannot be reused
- **Time-limited**: shares expire after 7 days if not opened
- **Revokable**: you can delete a sent share from the Shares tab before it's
  opened
- **Auditable**: both sender and recipient can see the share in their
  Shares history (who, when, article, note)

## Privacy

Sharing respects the app's privacy model:
- No article content leaves your server
- No personal notes or private state are shared
- The recipient cannot see your tags unless the tags feature is enabled for
  all users (tags are always visible if the feature is on)
- Share tokens are cryptographically random and unguessable
- Expired shares are automatically cleaned up by a daily job

## Requirements

Sharing requires:
- A working instance (single-user or multi-user)
- Recipient must have an account on the same instance
- No additional configuration needed — sharing is enabled by default

## Troubleshooting

If sharing doesn't work:
- **"Invalid or expired share"**: the link was already used or too old; ask
  the sender to resend
- **"User not found"**: double-check the recipient's username
- **"Sharing not available"**: contact your admin — on private instances,
  sharing can be disabled site-wide (though this is not the default)
- No notifications?: check your notification settings (bell icon → Settings)

Sharing works the same whether you're on desktop, tablet or mobile — the share dialog
and notifications adapt to the screen size.