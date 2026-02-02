package medic

import "testing"

func TestSendHeartbeat(t *testing.T) {
	type args struct {
		h Heartbeat
	}
	tests := []struct {
		name    string
		args    args
		wantErr bool
	}{
		// TODO: Add test cases.
		{
			name: "testing invalid name",
			args: args{
				h: Heartbeat{
					HeartbeatName: "Dont call me shirley",
					Service:       "fakeservice",
					Status:        "UP",
				},
			},
			wantErr: true,
		},
		{
			name: "testing no name",
			args: args{
				h: Heartbeat{
					HeartbeatName: "",
					Service:       "fakeservice",
					Status:        "UP",
				},
			},
			wantErr: true,
		},
		{
			name: "testing success",
			args: args{
				h: Heartbeat{
					HeartbeatName: "staging-fake-heartbeat-hb",
					Service:       "fakeservice",
					Status:        "UP",
				},
			},
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if err := SendHeartbeat(tt.args.h); (err != nil) != tt.wantErr {
				t.Errorf("SendHeartbeat() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
