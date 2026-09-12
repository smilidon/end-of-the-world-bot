// SPDX-License-Identifier: GPL-3.0-only
import java.io.*;
import java.util.*;
import net.osmand.binary.BinaryMapIndexReader;
import net.osmand.binary.BinaryMapAddressReaderAdapter.CityBlocks;
import net.osmand.data.City;
public class NamedPlaces {
 public static void main(String[] args) throws Exception {
  File f=new File(args[0]);
  BinaryMapIndexReader r=new BinaryMapIndexReader(new RandomAccessFile(f,"r"), f);
  try {
   System.out.println("OBF_VERSION\t"+r.getVersion());
   for(CityBlocks b:new CityBlocks[]{CityBlocks.CITY_TOWN_TYPE,CityBlocks.VILLAGES_TYPE})
    for(City c:r.getCities(null,b)) if(c.getLocation()!=null)
     for(int i=1;i<args.length;i++) if(c.getName().equalsIgnoreCase(args[i].trim()))
      System.out.println("PLACE\t"+i+"\t"+c.getId()+"\t"+c.getLocation().getLatitude()+"\t"+c.getLocation().getLongitude()+"\t"+c.getName().replace('\t',' ').replace('\n',' '));
  } finally {r.close();}
 }
}
