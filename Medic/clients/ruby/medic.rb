require 'logger'
require 'net/http'
require 'net/https'
require 'json'

# Default base URL, configurable via environment variable
DEFAULT_BASE_URL = 'https://medic.example.com'

# Get the Medic API base URL from environment or use default
def get_base_url
  ENV.fetch('MEDIC_BASE_URL', DEFAULT_BASE_URL)
end

# Send a heartbeat to the Medic service
#
# @param heartbeat_name [String] The name of the registered heartbeat
# @param service_name [String] The name of the associated service
# @param status [String] Current status (UP/DOWN/DEGRADED/etc)
# @param base_url [String, nil] Optional base URL override
# @param logger [Logger, nil] Optional logger instance
# @return [Net::HTTPResponse] The HTTP response
def sendHeartbeat(heartbeat_name, service_name, status, base_url: nil, logger: nil)
  logger ||= Logger.new($stdout)
  logger.level = Logger::WARN

  begin
    payload = {
      heartbeat_name: heartbeat_name,
      service_name: service_name,
      status: status
    }

    url = base_url || get_base_url
    uri = URI.parse("#{url}/heartbeat")

    res = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https') do |http|
      http.read_timeout = 30
      http.open_timeout = 10

      req = Net::HTTP::Post.new(uri)
      req['Content-Type'] = 'application/json'
      req.body = payload.to_json
      http.request(req)
    end

    res
  rescue StandardError => e
    logger.error("An error occurred when posting to Medic: #{e.message}")
    raise
  end
end
