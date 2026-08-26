{
  description = "Etiquette";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
    in {
      packages = nixpkgs.lib.genAttrs systems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in {
          default = pkgs.writeShellScriptBin "etiquette-server" ''
            exec ${pkgs.python3}/bin/python ${./label.py}
          '';
        }
      );

      devShells = nixpkgs.lib.genAttrs systems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in {
          default = pkgs.mkShell {
            packages = [
              pkgs.python3
              pkgs.typst
            ];
          };
        }
      );

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.services.etiquette-server;
        in {
          options.services.etiquette-server = {
            enable = lib.mkEnableOption "etiquette server";

            host = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1";
            };

            port = lib.mkOption {
              type = lib.types.port;
              default = 8000;
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.services.etiquette-server = {
              description = "Etiquette server";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];

              environment = {
                PYTHONUNBUFFERED = "1";
                ETIQUETTE_SERVER_HOST = cfg.host;
                ETIQUETTE_SERVER_PORT = toString cfg.port;
                ETIQUETTE_TYPST_BIN = "${pkgs.typst}/bin/typst";

                XDG_CACHE_HOME = "/var/cache/etiquette-server";
              };

              serviceConfig = {
                ExecStart =
                  "${self.packages.${pkgs.system}.default}/bin/etiquette-server";

                User = "etiquette-server";
                Group = "etiquette-server";

                Restart = "on-failure";
                RestartSec = "2s";

                PrivateTmp = true;
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = true;
                PrivateDevices = true;

                CacheDirectory = "etiquette-server";
              };

              path = [ pkgs.typst ];
            };

            users.users.etiquette-server = {
              isSystemUser = true;
              group = "etiquette-server";
            };

            users.groups.etiquette-server = {};
          };
        };
    };
}
