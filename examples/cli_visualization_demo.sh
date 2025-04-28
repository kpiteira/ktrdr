#!/bin/bash
# CLI Visualization Demo Script
# This script demonstrates the visualization CLI commands added in Task 3.4
# Run with: chmod +x cli_visualization_demo.sh && ./cli_visualization_demo.sh

# Set up colors for prettier output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== KTRDR CLI Visualization Demo ===${NC}"
echo -e "${YELLOW}This script demonstrates the visualization commands added in Task 3.4${NC}"
echo ""

# Create output directory if it doesn't exist
echo -e "${GREEN}Creating output directory...${NC}"
mkdir -p output
echo ""

# Show the help information for the plot command
echo -e "${GREEN}1. Displaying help for the 'plot' command:${NC}"
python ktrdr_cli.py plot --help
echo ""
sleep 1

# Show the help information for the plot-indicators command
echo -e "${GREEN}2. Displaying help for the 'plot-indicators' command:${NC}"
python ktrdr_cli.py plot-indicators --help
echo ""
sleep 1

# Create a basic candlestick chart with SMA indicator
echo -e "${GREEN}3. Creating a candlestick chart with SMA indicator overlay:${NC}"
echo -e "${YELLOW}Command: python ktrdr_cli.py plot MSFT --timeframe 1h --indicator SMA --period 20 --output output/demo_candlestick_sma.html${NC}"
python ktrdr_cli.py plot MSFT --timeframe 1h --indicator SMA --period 20 --output output/demo_candlestick_sma.html
echo ""
sleep 1

# Create a chart with RSI in a separate panel
echo -e "${GREEN}4. Creating a chart with RSI in a separate panel:${NC}"
echo -e "${YELLOW}Command: python ktrdr_cli.py plot MSFT --timeframe 1h --indicator RSI --period 14 --panel --output output/demo_rsi_panel.html${NC}"
python ktrdr_cli.py plot MSFT --timeframe 1h --indicator RSI --period 14 --panel --output output/demo_rsi_panel.html
echo ""
sleep 1

# Create a multi-indicator chart with default indicators
echo -e "${GREEN}5. Creating a multi-indicator chart with default indicators:${NC}"
echo -e "${YELLOW}Command: python ktrdr_cli.py plot-indicators MSFT --timeframe 1h --output output/demo_multi_indicator.html${NC}"
python ktrdr_cli.py plot-indicators MSFT --timeframe 1h --output output/demo_multi_indicator.html
echo ""
sleep 1

# Try with a different theme (light theme)
echo -e "${GREEN}6. Creating a chart with light theme:${NC}"
echo -e "${YELLOW}Command: python ktrdr_cli.py plot MSFT --timeframe 1h --theme light --indicator EMA --period 20 --output output/demo_light_theme.html${NC}"
python ktrdr_cli.py plot MSFT --timeframe 1h --theme light --indicator EMA --period 20 --output output/demo_light_theme.html
echo ""
sleep 1

# Show all the created files
echo -e "${GREEN}7. Generated HTML visualization files:${NC}"
ls -l output/demo_*.html
echo ""

echo -e "${BLUE}Demo complete! You can open the HTML files in your web browser to view the interactive charts.${NC}"
echo -e "${YELLOW}For example: open output/demo_multi_indicator.html${NC}"