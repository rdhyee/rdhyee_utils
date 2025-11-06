# Running macOS Utilities in the Cloud

## Overview

This repository contains several macOS-specific utilities that require macOS to run:

- **Bike Module** (`rdhyee_utils/bike/`) - Bike outliner app automation
- **Safari Module** (`rdhyee_utils/safari/`) - Safari browser automation
- **Google Chrome Module** (`rdhyee_utils/google_chrome/`) - Chrome automation
- **Clipboard Module** (`rdhyee_utils/clipboard/`) - macOS clipboard access via AppKit

These modules use macOS-specific technologies (appscript, AppKit) and cannot run on Linux or Windows.

## Platform Requirements

**macOS-Specific Modules** (~40% of codebase):
- Require physical Apple hardware or cloud Mac instances
- Need GUI environment for browser automation
- Require apps to be installed (Bike, Safari, Chrome)

**Cross-Platform Modules** (~60% of codebase):
- Google APIs (gmail, sheets, drive) - Work on any platform
- Core utilities - Platform-agnostic Python
- AWS, Selenium, Pandoc - Work on Linux with proper setup

## macOS Cloud Providers

### Official/Major Providers

#### 1. AWS EC2 Mac Instances
**Best for: Long-running sessions (24+ hours)**

- Dedicated Mac mini/Mac Studio hardware
- macOS versions: Monterey, Ventura, Sonoma
- Instance types:
  - `mac1.metal` - Intel-based Mac mini
  - `mac2.metal` - M1 Mac mini
  - `mac2-m2.metal` - M2 Mac mini
  - `mac2-m2pro.metal` - M2 Pro Mac mini
- **Minimum allocation: 24 hours** (dedicated host model)
- **Cost**: ~$1.08-$1.30/hour + 24hr minimum commitment
- **Good for**: CI/CD pipelines, iOS/macOS development
- **Documentation**: https://aws.amazon.com/ec2/instance-types/mac/

#### 2. MacStadium
**Best for: Long-term dedicated access**

- Specialized Mac hosting since 2011
- Hardware options: Mac mini, Mac Studio, Mac Pro
- Private cloud and Orka (Kubernetes for Mac)
- **Billing**: Hourly, monthly, or annual
- **Cost**: Starting ~$79/month for dedicated mini
- **Good for**: Xcode Cloud alternative, enterprise iOS CI/CD
- **Website**: https://www.macstadium.com

#### 3. Scaleway
**Best for: European-based, flexible hourly billing**

- Mac mini M1/M2 instances
- Based in Europe (Paris datacenter)
- **No 24-hour minimum** (more flexible than AWS)
- **Cost**: ~€0.60-1.00/hour
- **Good for**: Short-duration sessions, European users
- **Website**: https://www.scaleway.com/en/apple-silicon/

#### 4. Flow
**Best for: Sporadic, short-duration needs**

- Per-second billing for macOS VMs
- Mac Studio M1 Max/Ultra available
- On-demand scaling
- **Cost**: Per-second billing (~$0.50-2.00/hour equivalent)
- **Good for**: Bursty CI/CD workloads
- **Website**: https://www.flow.swiss

#### 5. Microsoft Azure
**Limited availability via MacStadium partnership**

- Not as widely available as AWS
- Similar pricing model to AWS
- Limited regions

### CI/CD-Specific Services

These services offer macOS runners for continuous integration but are **not suitable for general-purpose use**:

- **GitHub Actions** - macOS runners with Intel and Apple Silicon
- **CircleCI** - macOS executors
- **GitLab** - macOS shared runners
- **Buildkite** - Self-hosted or managed macOS agents
- **Bitrise** - Mobile-focused CI/CD
- **Codemagic** - Flutter and native mobile CI/CD

## Important Limitations

### Apple Licensing Restrictions

- **macOS can only legally run on Apple hardware** (per Apple EULA)
- Cloud providers use **physical Mac hardware**, not virtual machines
- Cannot run macOS in traditional VMs on non-Apple hardware

### Minimum Commitments

- **AWS**: 24-hour minimum allocation per dedicated host
- **Most providers**: Daily or monthly minimums
- **More expensive** than equivalent Linux/Windows instances

### Interactive Automation Challenges

For running utilities in this repository, you'll need:

1. **GUI Access**: VNC or Screen Sharing for Safari/Chrome automation
2. **App Installation**: Bike app must be installed and licensed
3. **Desktop Environment**: Full GUI session running (not headless)
4. **Network Configuration**: Proper firewall and security group setup

**Note**: Most cloud Mac instances are optimized for **headless CLI/CI/CD workflows**. Interactive app automation (like Safari/Chrome scripting) may require additional setup.

### Performance Considerations

- **Dedicated hardware** = Better, consistent performance
- **Apple Silicon (M1/M2)** generally faster than Intel for most tasks
- **Shared hardware** options are limited in the market
- **Network latency** affects VNC/remote desktop experience

## Recommendations for This Repository

### For Occasional Testing (< 24 hours/month)

1. **Scaleway** - No 24hr minimum, hourly billing
2. **Flow** - Per-second billing for very short sessions

### For Regular Development (> 24 hours/month)

1. **AWS EC2 Mac** - Mature, well-documented, integrates with AWS ecosystem
2. **MacStadium** - Flexible billing, specialized Mac hosting expertise

### For CI/CD Automation Only

1. **GitHub Actions** - If repo is on GitHub
2. **CircleCI/GitLab** - If already using these platforms

### For Local Development

If you have access to a physical Mac:
- **Use it directly** - Cheapest and most performant option
- **Set up remote access** via Screen Sharing or SSH
- **Run tests locally** before deploying to cloud

## Setup Checklist for Cloud macOS

When provisioning a cloud Mac for this repository:

- [ ] Choose provider based on usage pattern and budget
- [ ] Provision instance with appropriate macOS version
- [ ] Set up VNC/Screen Sharing for GUI access
- [ ] Install Xcode Command Line Tools
- [ ] Install Python 3.x
- [ ] Install required apps:
  - [ ] Bike outliner (if using bike module)
  - [ ] Safari (usually pre-installed)
  - [ ] Chrome (if using google_chrome module)
- [ ] Clone repository: `git clone https://github.com/rdhyee/rdhyee_utils.git`
- [ ] Install package: `pip install -e .`
- [ ] Set up credentials in `~/.credentials/` (for Google APIs)
- [ ] Configure 1Password CLI if needed: `op` command
- [ ] Test platform-agnostic modules first
- [ ] Test macOS-specific modules with GUI access

## Alternative: Hybrid Approach

Consider splitting workloads:

**Run on Linux/Local Machine:**
- Google APIs operations (Gmail, Sheets, Drive)
- Core utilities
- AWS operations
- Selenium with headless browsers

**Run on macOS (cloud or local):**
- Bike outliner automation
- Safari-specific automation
- Chrome macOS automation
- Clipboard operations

This minimizes expensive macOS cloud usage while maintaining full functionality.

## Cost Estimation Examples

### Scenario 1: Occasional Testing (2 hours/week)
- **Scaleway**: ~€0.80/hour × 8 hours/month = **~€6.40/month** (£5.60/$7.70)
- **AWS**: $1.20/hour × 24 hours minimum = **$28.80/day** (even for 2 hours use)

### Scenario 2: Daily Development (4 hours/day, 20 days/month)
- **AWS**: $1.20/hour × 24 hours × 20 days = **$576/month**
- **MacStadium**: Monthly dedicated mini = **$79-150/month** (better value)

### Scenario 3: CI/CD Pipeline (10 builds/day, 5 min each)
- **GitHub Actions**: macOS minutes at $0.08/min × 50 min/day × 30 days = **$120/month**
- **Flow**: Per-second billing = **$50-80/month** (more efficient)

## Further Reading

- [AWS Mac Instances Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)
- [Apple Developer Program](https://developer.apple.com/programs/) - For iOS/macOS development
- [MacStadium Blog](https://www.macstadium.com/blog) - Mac cloud hosting insights
- [Orka by MacStadium](https://orkadocs.macstadium.com/) - Kubernetes for Mac

## Questions?

For issues specific to this repository, open an issue at:
https://github.com/rdhyee/rdhyee_utils/issues
