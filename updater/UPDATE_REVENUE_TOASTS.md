# Revenue Split + Compact Toast Update

Implemented:
- Paid earnings now use immutable `LicenseSplit` records only.
- Pending/refunded/void licenses do not count toward earnings.
- Producer splits divide the producer pool evenly and preserve the final cent so totals remain exact.
- Messenger receives 10% of the full sale when the seller is not a producer; the remaining 90% is split between producers.
- Producer sale notifications now show the requested message format, including messenger share when applicable.
- Standard warning/info/error QMessageBox alerts are replaced globally by compact dark in-app toast notifications. Confirmation questions remain confirmations to avoid accidental destructive actions.
