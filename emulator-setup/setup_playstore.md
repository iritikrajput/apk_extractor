# Play Store Setup Guide

This guide explains how to set up Play Store on the Android emulator for APK extraction.

## Prerequisites

1. Android SDK installed with emulator
2. AVD created with `google_apis_playstore` system image
3. A valid Google account

## First-Time Setup

### Step 1: Start Emulator with GUI

For the first-time setup, start the emulator with GUI (not headless):

```bash
# Set Android SDK path
export ANDROID_HOME=~/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/emulator

# Start with GUI
emulator -avd playstore_device
```

### Step 2: Initial Boot

Wait for the emulator to fully boot. This can take 2-5 minutes on the first boot.

You'll see the Android lock screen when ready.

### Step 3: Open Play Store

1. Unlock the device (swipe up)
2. Find the Play Store app in the app drawer
3. Tap to open

### Step 4: Sign In

1. Tap "Sign in"
2. Enter your Google account email
3. Enter your password
4. Accept terms and conditions

> **Note**: Use a dedicated Google account for testing, not your personal account.

### Step 5: Complete Setup

1. Accept Google Play terms
2. Choose backup preferences (can skip)
3. Skip payment setup (not needed)
4. Wait for Play Store to finish loading

### Step 6: Test Installation

Install a test app to verify everything works:

1. Search for a small app (e.g., "Calculator")
2. Tap "Install"
3. Wait for download and installation
4. Verify app appears in app drawer

### Step 7: Extract APK

Now you can extract the APK:

```bash
# Check installed packages
adb shell pm list packages | grep calculator

# Get APK path
adb shell pm path com.google.android.calculator

# Pull APK
adb pull /data/app/.../base.apk ./calculator.apk
```

## Headless Mode

After initial setup, you can run headless:

```bash
./emulator-setup/start_emulator.sh
```

The Play Store login persists in the AVD.

## Troubleshooting

### Play Store Not Opening

1. Ensure you're using `google_apis_playstore` system image
2. Check internet connectivity in emulator
3. Try: Settings > Apps > Play Store > Clear Data

### Login Issues

1. Enable "Less secure app access" for the Google account
2. Try creating a new Google account for testing
3. Check if account has 2FA (may need app password)

### App Not Installing

1. Check available storage in emulator
2. Some apps require device certification
3. Region restrictions may apply

### Certification Issues

Some apps require device certification (SafetyNet). Most apps work without it, but some banking/streaming apps may not.

## Tips

### Speed Up Emulator

1. Enable KVM on Linux:
   ```bash
   sudo modprobe kvm
   ```

2. Use hardware acceleration:
   ```bash
   emulator -avd playstore_device -gpu host
   ```

3. Allocate more RAM:
   ```bash
   emulator -avd playstore_device -memory 4096
   ```

### Persist Data

The AVD stores all data in:
```
~/.android/avd/playstore_device.avd/
```

To backup Play Store login:
```bash
# Create snapshot
adb emu avd snapshot save playstore_setup

# Later restore
adb emu avd snapshot load playstore_setup
```

### Multiple Accounts

You can add multiple Google accounts for testing different regions:

1. Settings > Accounts > Add Account
2. Sign in with different Google account
3. Switch accounts in Play Store

## Security Notes

1. **Use dedicated test accounts** - Don't use personal Google accounts
2. **Don't store credentials** - Use environment variables
3. **Network isolation** - Consider running emulator in isolated network
4. **Regular cleanup** - Remove extracted APKs after analysis
5. **Legal compliance** - Only extract apps you have rights to analyze
