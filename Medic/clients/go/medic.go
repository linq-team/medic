package medic

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

// DefaultBaseURL is the default Medic API base URL
const DefaultBaseURL = "https://medic.example.com"

var (
	httpClient = &http.Client{
		Timeout: 30 * time.Second,
	}
)

// Heartbeat represents the heartbeat configuration
type Heartbeat struct {
	HeartbeatName string `validate:"required" json:"heartbeat_name"`
	Service       string `json:"service_name"`
	Status        string `json:"status"`
}

// Client represents a Medic API client
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewClient creates a new Medic client with the given base URL
// If baseURL is empty, it will use MEDIC_BASE_URL env var or the default
func NewClient(baseURL string) *Client {
	if baseURL == "" {
		baseURL = os.Getenv("MEDIC_BASE_URL")
		if baseURL == "" {
			baseURL = DefaultBaseURL
		}
	}
	return &Client{
		BaseURL:    baseURL,
		HTTPClient: httpClient,
	}
}

// GetBaseURL returns the Medic API base URL from environment or default
func GetBaseURL() string {
	if url := os.Getenv("MEDIC_BASE_URL"); url != "" {
		return url
	}
	return DefaultBaseURL
}

// SendHeartbeat sends a heartbeat post to medic using the default client
func SendHeartbeat(h Heartbeat) error {
	return NewClient("").SendHeartbeat(h)
}

// SendHeartbeat sends a heartbeat post to medic
func (c *Client) SendHeartbeat(h Heartbeat) error {
	// Configure the body content
	var body bytes.Buffer
	if err := json.NewEncoder(&body).Encode(h); err != nil {
		return fmt.Errorf("failed to encode heartbeat: %w", err)
	}

	// Make the request to medic
	url := fmt.Sprintf("%s/heartbeat", c.BaseURL)
	resp, err := c.HTTPClient.Post(url, "application/json", &body)
	if err != nil {
		log.Printf("Failed to post heartbeat in Medic: %v, Heartbeat: %s", err, h.HeartbeatName)
		return fmt.Errorf("heartbeat post failure: %w", err)
	}
	defer resp.Body.Close()

	// Check the status code for success
	if resp.StatusCode >= 300 {
		log.Printf("Failed to post heartbeat in Medic: Status_Code: %d, Heartbeat: %s", resp.StatusCode, h.HeartbeatName)
		return fmt.Errorf("unexpected status code %d", resp.StatusCode)
	}

	return nil
}
